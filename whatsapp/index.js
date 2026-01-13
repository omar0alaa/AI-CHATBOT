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
const { getStore, userStore } = require('./db');

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

const sessions = new Map(); // account -> { sock, currentQR, connectionState, lastStatusAt }
const sseClients = new Map(); // account -> Set<res>
const stream515Count = new Map(); // account -> consecutive 515 stream errors

function getSession(account) {
  return sessions.get(account);
}

function ensureSseSet(account) {
  if (!sseClients.has(account)) sseClients.set(account, new Set());
  return sseClients.get(account);
}

function setStatus(account, state) {
  const sess = sessions.get(account);
  if (sess) {
    sess.connectionState = state;
    sess.lastStatusAt = Date.now();
  }
  broadcastStatus(account);
}

function broadcastStatus(account) {
  const sess = sessions.get(account) || {};
  const payload = JSON.stringify({
    type: 'status',
    data: {
      connection: sess.connectionState || 'init',
      deviceName: DEVICE_NAME,
      lastStatusAt: sess.lastStatusAt || Date.now(),
      hasQR: !!sess.currentQR,
    },
  });
  for (const res of ensureSseSet(account)) {
    res.write(`data: ${payload}\n\n`);
  }
}

function broadcastMessage(account, jid) {
  const payload = JSON.stringify({ type: 'message', data: { jid } });
  for (const res of ensureSseSet(account)) {
    res.write(`data: ${payload}\n\n`);
  }
}

function broadcastQr(account, qr) {
  const payload = JSON.stringify({ type: 'qr', data: { qr } });
  for (const res of ensureSseSet(account)) {
    res.write(`data: ${payload}\n\n`);
  }
}

function authPathFor(account) {
  const safe = account.replace(/[^a-zA-Z0-9_-]/g, '_');
  return path.join(AUTH_FOLDER, safe);
}

async function ensureWhatsApp(account) {
  if (sessions.has(account)) return sessions.get(account).sock;
  const authDir = authPathFor(account);
  const { state, saveCreds } = await useMultiFileAuthState(authDir);
  const { version } = await fetchLatestBaileysVersion();
  const sock = makeWASocket({
    version,
    printQRInTerminal: true,
    auth: state,
    logger,
    browser: [DEVICE_NAME, 'Chrome', '4.0'],
    markOnlineOnConnect: false,
    syncFullHistory: false,
  });

  const store = getStore(account);
  sessions.set(account, {
    sock,
    currentQR: null,
    connectionState: 'init',
    lastStatusAt: Date.now(),
    store,
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;
    const sess = sessions.get(account);

    if (qr && sess) {
      try {
        sess.currentQR = await QRCode.toDataURL(qr);
        qrcodeTerm.generate(qr, { small: true });
      } catch (err) {
        logger.error(err, 'Failed to render QR');
      }
      broadcastStatus(account);
      broadcastQr(account, sess.currentQR);
    }

    if (connection === 'close') {
      setStatus(account, 'close');
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      logger.warn({ account, reason: lastDisconnect?.error }, 'WhatsApp connection closed');
      if (statusCode === 515) {
        const count = (stream515Count.get(account) || 0) + 1;
        stream515Count.set(account, count);
        if (count >= 2) {
          logger.warn({ account, count }, 'Encountered stream error 515 repeatedly; clearing auth and forcing relink');
          try { await fs.promises.rm(authPathFor(account), { recursive: true, force: true }); } catch (e) { logger.error(e, 'Failed to clear auth folder'); }
          sessions.delete(account);
          stream515Count.set(account, 0);
        } else {
          logger.warn({ account, count }, 'Encountered stream error 515; retrying without clearing auth');
        }
      }
      if (shouldReconnect) {
        ensureWhatsApp(account).catch((err) => logger.error(err, 'Reconnect failed'));
      } else {
        logger.error('Logged out from WhatsApp. Delete auth folder to re-auth.');
      }
    } else if (connection === 'open') {
      if (sess) sess.currentQR = null;
      setStatus(account, 'open');
      stream515Count.set(account, 0);
      logger.info({ account }, 'WhatsApp connection established');
    } else if (connection) {
      setStatus(account, connection);
    }
  });

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify' || !messages) return;
    for (const msg of messages) {
      try {
        await captureMessage(account, msg);
        if (!msg.key.fromMe) {
          await handleIncoming(account, sock, msg);
        }
      } catch (err) {
        logger.error(err, 'Failed processing message');
      }
    }
  });

  return sock;
}

async function waitForQr(account, timeoutMs = 20000) {
  const start = Date.now();
  await ensureWhatsApp(account);
  while (Date.now() - start < timeoutMs) {
    const qr = getSession(account)?.currentQR;
    if (qr) return qr;
    await new Promise((r) => setTimeout(r, 500));
  }
  return null;
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

async function captureMessage(account, msg) {
  const remoteJid = msg.key.remoteJid || '';
  if (!remoteJid || remoteJid.endsWith('@status')) return;

  const text = extractText(msg);
  const fromMe = !!msg.key.fromMe;
  if (fromMe) return; // Outbound messages are stored at send time
  const isGroup = remoteJid.endsWith('@g.us');
  const tsSeconds = Number(msg.messageTimestamp || Date.now());
  const ts = Number.isFinite(tsSeconds) ? tsSeconds * 1000 : Date.now();

  const store = getStore(account);
  store.saveMessage({
    jid: remoteJid,
    fromMe,
    text,
    ts,
    keyId: msg.key.id,
    name: msg.pushName,
    isGroup,
  });
  broadcastMessage(account, remoteJid);
}

async function handleIncoming(account, sock, msg) {
  const remoteJid = msg.key.remoteJid || '';
  if (remoteJid.endsWith('@status')) return;

  const text = extractText(msg);
  if (!text) return;

  const store = getStore(account);
  const chatMeta = store.getChat(remoteJid);
  if (chatMeta?.muted) {
    logger.info({ account, from: remoteJid }, 'Chat muted; skipping AI reply');
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
    store.saveMessage({
      jid: remoteJid,
      fromMe: true,
      text: reply,
      ts: Date.now(),
      keyId: null,
      name: DEVICE_NAME,
      isGroup: remoteJid.endsWith('@g.us'),
    });
    broadcastMessage(account, remoteJid);
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
    ensureWhatsApp(username).catch((err) => logger.error(err, 'Failed to start WA session'));
    res.json({ ok: true, user: { username } });
  });

  app.post('/api/logout', (req, res) => {
    req.session.destroy(() => {
      res.json({ ok: true });
    });
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
    if (userStore.hasUsers() && !req.session?.user) return res.status(401).json({ error: 'Unauthorized' });
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

  app.get('/api/status', requireLogin, async (req, res) => {
    const account = req.session.user.username;
    await ensureWhatsApp(account);
    const sess = getSession(account) || {};
    res.json({ connection: sess.connectionState || 'init', deviceName: DEVICE_NAME, lastStatusAt: sess.lastStatusAt || Date.now(), hasQR: !!sess.currentQR });
  });

  app.get('/api/qr', requireLogin, async (req, res) => {
    const account = req.session.user.username;
    const qr = await waitForQr(account);
    if (!qr) return res.status(404).json({ error: 'No QR available yet' });
    res.json({ qr });
  });

  app.get('/api/chats', requireLogin, async (req, res) => {
    const account = req.session.user.username;
    await ensureWhatsApp(account);
    const store = getStore(account);
    const limit = Number(req.query.limit || 200);
    const offset = Number(req.query.offset || 0);
    res.json({ chats: store.listChats(limit, offset) });
  });

  app.post('/api/chats/:jid/mute', requireLogin, (req, res) => {
    const account = req.session.user.username;
    const store = getStore(account);
    const muted = !!req.body?.muted;
    store.setMuted(req.params.jid, muted);
    res.json({ ok: true, muted });
  });

  app.get('/api/chats/:jid/messages', requireLogin, (req, res) => {
    const account = req.session.user.username;
    const store = getStore(account);
    const limit = Number(req.query.limit || 50);
    const offset = Number(req.query.offset || 0);
    res.json({ messages: store.getMessages(req.params.jid, limit, offset) });
  });

  app.post('/api/chats/:jid/send', requireLogin, async (req, res) => {
    const account = req.session.user.username;
    const store = getStore(account);
    const sock = await ensureWhatsApp(account);
    const text = (req.body?.text || '').trim();
    if (!text) return res.status(400).json({ error: 'text required' });
    if (!sock) return res.status(503).json({ error: 'WhatsApp socket not ready' });
    try {
      await sock.sendMessage(req.params.jid, { text });
      store.saveMessage({
        jid: req.params.jid,
        fromMe: true,
        text,
        ts: Date.now(),
        keyId: null,
        name: 'Admin',
        isGroup: req.params.jid.endsWith('@g.us'),
      });
      broadcastMessage(account, req.params.jid);
      res.json({ ok: true });
    } catch (err) {
      logger.error(err, 'Failed to send admin message');
      res.status(500).json({ error: 'failed to send' });
    }
  });

  app.post('/api/unlink', requireLogin, async (req, res) => {
    const account = req.session.user.username;
    try {
      await fs.promises.rm(authPathFor(account), { recursive: true, force: true });
      const sess = sessions.get(account);
      if (sess?.sock?.end) {
        try { sess.sock.end(); } catch (err) { logger.warn(err, 'Failed to end socket'); }
      }
      sessions.delete(account);
      setStatus(account, 'restarting');
      ensureWhatsApp(account).catch((err) => logger.error(err, 'Restart after unlink failed'));
      res.json({ ok: true });
    } catch (err) {
      logger.error(err, 'Failed to unlink');
      res.status(500).json({ error: 'failed to unlink' });
    }
  });

  app.get('/api/events', requireLogin, async (req, res) => {
    const account = req.session.user.username;
    await ensureWhatsApp(account);
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.flushHeaders?.();
    ensureSseSet(account).add(res);
    req.on('close', () => ensureSseSet(account).delete(res));
    const initial = JSON.stringify({
      type: 'status',
      data: { connection: getSession(account)?.connectionState || 'init', deviceName: DEVICE_NAME, lastStatusAt: getSession(account)?.lastStatusAt || Date.now(), hasQR: !!getSession(account)?.currentQR },
    });
    res.write(`data: ${initial}\n\n`);
    const currentQR = getSession(account)?.currentQR;
    if (currentQR) {
      const qrMsg = JSON.stringify({ type: 'qr', data: { qr: currentQR } });
      res.write(`data: ${qrMsg}\n\n`);
    }
  });

  app.listen(ADMIN_PORT, () => {
    logger.info(`WhatsApp admin UI: http://localhost:${ADMIN_PORT}/admin`);
  });
}

userStore.ensureDefaultUser();
startHttpServer();
