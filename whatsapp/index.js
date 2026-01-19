'use strict';

const fs = require('fs');
const path = require('path');
const { webcrypto } = require('crypto');
const axios = require('axios');
const pino = require('pino');
const qrcodeTerm = require('qrcode-terminal');
const QRCode = require('qrcode');
const express = require('express');
const cors = require('cors');
const session = require('express-session');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} = require('@whiskeysockets/baileys');
const db = require('./db');
const { userStore } = db;

require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const CHATBOT_API_URL = process.env.CHATBOT_API_URL || 'http://161.97.147.7:5000/api/chat';
const CHATBOT_LANG = process.env.CHATBOT_LANG || 'en';
const AUTH_FOLDER = process.env.WHATSAPP_AUTH_DIR || path.join(__dirname, 'auth_info');
const DEVICE_NAME = process.env.WHATSAPP_DEVICE_NAME || 'YouLearnt Bot';
const LOG_LEVEL = process.env.WHATSAPP_LOG_LEVEL || 'info';
const REPLY_TIMEOUT_MS = parseInt(process.env.WHATSAPP_API_TIMEOUT || '20000', 10);
const ADMIN_PORT = parseInt(process.env.WHATSAPP_ADMIN_PORT || '4000', 10);
const SESSION_SECRET = process.env.WHATSAPP_SESSION_SECRET || 'change-me-session-secret';
const SESSION_MAX_AGE = parseInt(process.env.WHATSAPP_SESSION_MAX_AGE || '86400000', 10);

const logger = pino({ level: LOG_LEVEL });

if (!globalThis.crypto) {
  globalThis.crypto = webcrypto;
}

let waSock = null;
let currentQR = null;
let connectionState = 'init';
let lastStatusAt = Date.now();
let ownerJid = null;
const sseClients = new Set();
let autoBackfillTimer = null;

function stripDevice(jid = '') {
  return jid.split(':')[0];
}

async function backfillChatHistory(jid, days = 30) {
  const sinceMs = Date.now() - days * 86400000;
  if (!waSock) return 0;
  try {
    const msgs = await waSock.fetchMessagesFromWA(jid, 500, { startTimestamp: Math.floor(sinceMs / 1000) });
    let saved = 0;
    msgs
      .map(mapFetchedMessage)
      .filter(Boolean)
      .forEach((m) => {
        db.saveMessage(m);
        fetchAndStoreProfilePic(m.jid);
        saved += 1;
      });
    if (saved > 0) broadcastMessage(jid);
    return saved;
  } catch (err) {
    logger.warn({ err, jid }, 'Backfill failed');
    return 0;
  }
}

async function backfillAllKnownChats(days = 30) {
  if (!waSock) return;
  const baseOwner = stripDevice(ownerJid || '');
  const chats = db.listChats(500, 0, true).filter((c) => stripDevice(c.jid) !== baseOwner);
  for (const chat of chats) {
    await backfillChatHistory(chat.jid, days);
  }
}

function setStatus(state) {
  connectionState = state;
  lastStatusAt = Date.now();
  broadcastStatus();
}

function broadcastStatus() {
  const payload = JSON.stringify({
    type: 'status',
    data: { connection: connectionState, deviceName: DEVICE_NAME, lastStatusAt, hasQR: !!currentQR, userJid: ownerJid },
  });
  for (const res of sseClients) {
    res.write(`data: ${payload}\n\n`);
  }
}

function broadcastMessage(jid) {
  const payload = JSON.stringify({ type: 'message', data: { jid } });
  for (const res of sseClients) {
    res.write(`data: ${payload}\n\n`);
  }
}

async function startWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_FOLDER);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    printQRInTerminal: true,
    auth: state,
    logger,
    browser: [DEVICE_NAME, 'Chrome', '4.0'],
    markOnlineOnConnect: false,
    // Enable initial history/chat sync so we receive chat metadata to seed backfill
    syncFullHistory: true,
  });

  waSock = sock;

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      try {
        currentQR = await QRCode.toDataURL(qr);
        qrcodeTerm.generate(qr, { small: true });
      } catch (err) {
        logger.error(err, 'Failed to render QR');
      }
      broadcastStatus();
    }

    if (connection === 'close') {
      setStatus('close');
      const shouldReconnect =
        lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
      logger.warn({ reason: lastDisconnect?.error }, 'WhatsApp connection closed');
      if (shouldReconnect) {
        startWhatsApp().catch((err) => logger.error(err, 'Reconnect failed'));
      } else {
        logger.error('Logged out from WhatsApp. Delete auth_info folder to re-auth.');
      }
    } else if (connection === 'open') {
      currentQR = null;
      ownerJid = sock.user?.id || ownerJid;
      setStatus('open');
      logger.info('WhatsApp connection established');
      if (autoBackfillTimer) clearTimeout(autoBackfillTimer);
      autoBackfillTimer = setTimeout(() => {
        backfillAllKnownChats(30).catch((err) => logger.warn({ err }, 'Auto backfill failed'));
      }, 3000);
    } else if (connection) {
      setStatus(connection);
    }
  });

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify' || !messages) return;
    for (const msg of messages) {
      try {
        await captureMessage(msg);
        if (!msg.key.fromMe) {
          await handleIncoming(sock, msg);
        }
      } catch (err) {
        logger.error(err, 'Failed processing message');
      }
    }
  });

  sock.ev.on('chats.upsert', async ({ chats }) => {
    if (!chats?.length) return;
    chats.forEach((c) => {
      const jid = c.id || c.jid;
      if (!jid) return;
      const lastTsRaw = c.lastMessage?.messageTimestamp || c.conversationTimestamp;
      const lastTs = lastTsRaw ? Number(lastTsRaw) * 1000 : null;
      const preview = c.lastMessage?.message
        ? extractText({ message: c.lastMessage.message, key: { remoteJid: jid, fromMe: false }, messageTimestamp: c.lastMessage?.messageTimestamp })
        : c.lastMessage?.conversation || '';
      db.upsertChatMeta({
        jid,
        name: c.name || c.subject || null,
        isGroup: jid.endsWith('@g.us'),
        lastMessage: preview || null,
        lastTs,
        unread: c.unreadCount || 0,
        muted: c.muteEndTime ? 1 : 0,
        archived: c.archive ? 1 : 0,
      });
      fetchAndStoreProfilePic(jid);
    });
  });
}

function extractText(msg) {
  const m = msg.message || {};
  if (m.conversation) return m.conversation.trim();
  if (m.extendedTextMessage?.text) return m.extendedTextMessage.text.trim();
  if (m.ephemeralMessage?.message) {
    return extractText({ ...msg, message: m.ephemeralMessage.message });
  }
  return '';
}

async function fetchAndStoreProfilePic(jid) {
  try {
    const existing = db.getChat(jid);
    if (existing?.profilePic) return existing.profilePic;
    if (!waSock?.profilePictureUrl) return null;
    const url = await waSock.profilePictureUrl(jid, 'image');
    if (!url) return null;
    const resp = await axios.get(url, { responseType: 'arraybuffer' });
    const base64 = 'data:image/jpeg;base64,' + Buffer.from(resp.data, 'binary').toString('base64');
    db.setProfilePic(jid, base64);
    return base64;
  } catch (err) {
    logger.debug({ err }, 'Failed to fetch profile picture');
    return null;
  }
}

async function captureMessage(msg) {
  const remoteJid = msg.key.remoteJid || '';
  if (!remoteJid || remoteJid.endsWith('@status')) return;

  const text = extractText(msg);
  const baseRemote = stripDevice(remoteJid);
  const baseOwner = stripDevice(ownerJid || '');
  if (baseOwner && baseRemote === baseOwner) return;
  if (!text) return;
  const fromMe = !!msg.key.fromMe;
  const isGroup = remoteJid.endsWith('@g.us');
  const tsSeconds = Number(msg.messageTimestamp || Date.now());
  const ts = Number.isFinite(tsSeconds) ? tsSeconds * 1000 : Date.now();

  db.saveMessage({
    jid: remoteJid,
    fromMe,
    text,
    ts,
    keyId: msg.key.id,
    name: msg.pushName,
    isGroup,
  });
  fetchAndStoreProfilePic(remoteJid);
  broadcastMessage(remoteJid);
}

function mapFetchedMessage(msg) {
  const remoteJid = msg.key?.remoteJid || '';
  if (!remoteJid || remoteJid.endsWith('@status')) return null;
  const text = extractText(msg);
  if (!text) return null;
  const tsSeconds = Number(msg.messageTimestamp || Date.now());
  const ts = Number.isFinite(tsSeconds) ? tsSeconds * 1000 : Date.now();
  return {
    jid: remoteJid,
    fromMe: !!msg.key?.fromMe,
    text,
    ts,
    keyId: msg.key?.id,
    name: msg.pushName,
    isGroup: remoteJid.endsWith('@g.us'),
  };
}

async function handleIncoming(sock, msg) {
  const remoteJid = msg.key.remoteJid || '';
  if (remoteJid.endsWith('@status')) return;

  const text = extractText(msg);
  if (!text) return;

  const chatMeta = db.getChat(remoteJid);
  if (chatMeta?.muted) {
    logger.info({ from: remoteJid }, 'Chat muted; skipping AI reply');
    return;
  }

  logger.info({ from: remoteJid, text }, 'Incoming message');

  try {
    const response = await axios.post(
      CHATBOT_API_URL,
      { message: text, lang: CHATBOT_LANG },
      { timeout: REPLY_TIMEOUT_MS }
    );

    const reply = response?.data?.message || 'Sorry, I could not get a reply right now.';

    await sock.sendMessage(remoteJid, { text: reply }, { quoted: msg });
    db.saveMessage({
      jid: remoteJid,
      fromMe: true,
      text: reply,
      ts: Date.now(),
      keyId: null,
      name: DEVICE_NAME,
      isGroup: remoteJid.endsWith('@g.us'),
    });
    broadcastMessage(remoteJid);
  } catch (err) {
    logger.error(err, 'Chatbot request failed');
    await sock.sendMessage(
      remoteJid,
      {
        text: 'Sorry, I could not respond right now. Please try again later.',
      },
      { quoted: msg }
    );
  }
}

function requireLogin(req, res, next) {
  if (req.session && req.session.user) return next();
  return res.status(401).json({ error: 'Unauthorized' });
}

function startHttpServer() {
  const app = express();
  app.use(express.json({ limit: '1mb' }));
  app.use(cors({ origin: true, credentials: true }));
  app.use(session({
    secret: SESSION_SECRET,
    resave: false,
    saveUninitialized: false,
    cookie: { maxAge: SESSION_MAX_AGE, httpOnly: true },
  }));
  app.use('/admin', express.static(path.join(__dirname, 'admin')));

  app.post('/api/login', (req, res) => {
    const { username, password } = req.body || {};
    const user = userStore.getUser(username);
    if (!user || !userStore.verifyPassword(password, user.password_hash)) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    req.session.user = { username };
    res.json({ ok: true, user: { username } });
  });

  app.post('/api/logout', (req, res) => {
    req.session.destroy(() => res.json({ ok: true }));
  });

  app.get('/api/me', (req, res) => {
    if (req.session?.user) return res.json({ user: req.session.user });
    return res.status(401).json({ error: 'Unauthorized' });
  });

  app.get('/api/users/exists', (req, res) => {
    res.json({ hasUsers: userStore.hasUsers() });
  });

  app.post('/api/users', (req, res) => {
    const { username, password } = req.body || {};
    if (!username || !password) return res.status(400).json({ error: 'username and password required' });

    // Allow unauthenticated signup only when there are no users or only the bootstrap admin
    let allowUnauthedCreate = false;
    try {
      const users = userStore.listUsers ? userStore.listUsers() : [];
      const count = Array.isArray(users) ? users.length : 0;
      const onlyDefaultAdmin = count === 1 && users[0]?.username === 'admin';
      allowUnauthedCreate = count === 0 || onlyDefaultAdmin;
    } catch (err) {
      logger.warn({ err }, 'Failed to inspect existing users');
      allowUnauthedCreate = !userStore.hasUsers();
    }

    if (!allowUnauthedCreate && !req.session?.user) return res.status(401).json({ error: 'Unauthorized' });
    try {
      userStore.createUser(username.trim(), password);
      res.json({ ok: true, user: { username } });
    } catch (err) {
      if (err.code === 'SQLITE_CONSTRAINT_UNIQUE') {
        return res.status(409).json({ error: 'User exists' });
      }
      logger.error(err, 'Failed to create user');
      res.status(500).json({ error: 'Failed to create user' });
    }
  });

  app.get('/api/status', requireLogin, (req, res) => {
    res.json({ connection: connectionState, deviceName: DEVICE_NAME, lastStatusAt, hasQR: !!currentQR, userJid: ownerJid });
  });

  app.get('/api/qr', requireLogin, (req, res) => {
    if (!currentQR) return res.status(404).json({ error: 'No QR available' });
    res.json({ qr: currentQR });
  });

  app.get('/api/chats', requireLogin, (req, res) => {
    const limit = Number(req.query.limit || 200);
    const offset = Number(req.query.offset || 0);
    const includeArchived = req.query.includeArchived === '1' || req.query.includeArchived === 'true';
    const baseOwner = stripDevice(ownerJid || '');
    const chats = db.listChats(limit, offset, includeArchived).filter((c) => {
      const base = stripDevice(c.jid);
      const nameOrJid = (c.name || c.jid || '').toLowerCase();
      const isSystem = nameOrJid.includes('@s.whatsapp.net');
      return (!baseOwner || base !== baseOwner) && !isSystem;
    });
    chats.forEach((c) => { if (!c.profilePic) fetchAndStoreProfilePic(c.jid); });
    res.json({ chats });
  });

  app.post('/api/chats/:jid/mute', requireLogin, (req, res) => {
    const muted = !!req.body?.muted;
    db.setMuted(req.params.jid, muted);
    res.json({ ok: true, muted });
  });

  app.get('/api/chats/:jid/messages', requireLogin, (req, res) => {
    const limit = Number(req.query.limit || 50);
    const offset = Number(req.query.offset || 0);
    res.json({ messages: db.getMessages(req.params.jid, limit, offset) });
  });

  app.post('/api/chats/:jid/send', requireLogin, async (req, res) => {
    const text = (req.body?.text || '').trim();
    if (!text) return res.status(400).json({ error: 'text required' });
    if (!waSock) return res.status(503).json({ error: 'WhatsApp socket not ready' });
    try {
      await waSock.sendMessage(req.params.jid, { text });
      db.saveMessage({
        jid: req.params.jid,
        fromMe: true,
        text,
        ts: Date.now(),
        keyId: null,
        name: 'Admin',
        isGroup: req.params.jid.endsWith('@g.us'),
      });
      broadcastMessage(req.params.jid);
      res.json({ ok: true });
    } catch (err) {
      logger.error(err, 'Failed to send admin message');
      res.status(500).json({ error: 'failed to send' });
    }
  });

  app.post('/api/chats/:jid/backfill', requireLogin, async (req, res) => {
    const days = Number(req.body?.days || 30);
    if (!waSock) return res.status(503).json({ error: 'WhatsApp socket not ready' });
    try {
      const saved = await backfillChatHistory(req.params.jid, days);
      res.json({ ok: true, saved });
    } catch (err) {
      logger.error(err, 'Backfill failed');
      res.status(500).json({ error: 'backfill failed' });
    }
  });

  app.post('/api/chats/:jid/archive', requireLogin, (req, res) => {
    const archived = req.body?.archived !== false;
    db.archiveChat(req.params.jid, archived);
    res.json({ ok: true, archived });
  });

  app.delete('/api/chats/:jid', requireLogin, (req, res) => {
    db.deleteChat(req.params.jid);
    res.json({ ok: true });
  });

  app.post('/api/unlink', requireLogin, async (req, res) => {
    try {
      await fs.promises.rm(AUTH_FOLDER, { recursive: true, force: true });
      currentQR = null;
      setStatus('restarting');
      if (waSock?.end) {
        try { waSock.end(); } catch (err) { logger.warn(err, 'Failed to end socket'); }
      }
      startWhatsApp().catch((err) => logger.error(err, 'Restart after unlink failed'));
      res.json({ ok: true });
    } catch (err) {
      logger.error(err, 'Failed to unlink');
      res.status(500).json({ error: 'failed to unlink' });
    }
  });

  app.get('/api/events', requireLogin, (req, res) => {
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.flushHeaders?.();
    sseClients.add(res);
    req.on('close', () => sseClients.delete(res));
    // Send initial status
    const initial = JSON.stringify({
      type: 'status',
      data: { connection: connectionState, deviceName: DEVICE_NAME, lastStatusAt, hasQR: !!currentQR, userJid: ownerJid },
    });
    res.write(`data: ${initial}\n\n`);
  });

  app.listen(ADMIN_PORT, () => {
    logger.info(`WhatsApp admin UI: http://localhost:${ADMIN_PORT}/admin`);
  });
}

startHttpServer();
startWhatsApp().catch((err) => {
  logger.error(err, 'WhatsApp bridge failed to start');
  process.exit(1);
});
userStore.ensureDefaultUser();
