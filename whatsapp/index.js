'use strict';

const path = require('path');
const axios = require('axios');
const pino = require('pino');
const qrcode = require('qrcode-terminal');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} = require('@whiskeysockets/baileys');

// Load env from project root
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const CHATBOT_API_URL = process.env.CHATBOT_API_URL || 'http://127.0.0.1:5000/api/chat';
const CHATBOT_LANG = process.env.CHATBOT_LANG || 'en';
const AUTH_FOLDER = process.env.WHATSAPP_AUTH_DIR || path.join(__dirname, 'auth_info');
const DEVICE_NAME = process.env.WHATSAPP_DEVICE_NAME || 'YouLearnt Bot';
const LOG_LEVEL = process.env.WHATSAPP_LOG_LEVEL || 'info';
const REPLY_TIMEOUT_MS = parseInt(process.env.WHATSAPP_API_TIMEOUT || '20000', 10);

const logger = pino({ level: LOG_LEVEL });

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_FOLDER);
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

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      qrcode.generate(qr, { small: true });
    }

    if (connection === 'close') {
      const shouldReconnect =
        lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
      logger.warn({ reason: lastDisconnect?.error }, 'WhatsApp connection closed');
      if (shouldReconnect) {
        start().catch((err) => logger.error(err, 'Reconnect failed'));
      } else {
        logger.error('Logged out from WhatsApp. Delete auth_info folder to re-auth.');
      }
    } else if (connection === 'open') {
      logger.info('WhatsApp connection established');
    }
  });

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify' || !messages) return;
    for (const msg of messages) {
      await handleMessage(sock, msg).catch((err) =>
        logger.error(err, 'Failed to handle incoming message')
      );
    }
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

async function handleMessage(sock, msg) {
  const remoteJid = msg.key.remoteJid || '';

  if (msg.key.fromMe) return; // ignore echoes
  if (remoteJid.endsWith('@status')) return; // ignore status updates

  const text = extractText(msg);
  if (!text) return;

  logger.info({ from: remoteJid, text }, 'Incoming message');

  try {
    const response = await axios.post(
      CHATBOT_API_URL,
      { message: text, lang: CHATBOT_LANG },
      { timeout: REPLY_TIMEOUT_MS }
    );

    const reply = response?.data?.message || 'Sorry, I could not get a reply right now.';

    await sock.sendMessage(
      remoteJid,
      { text: reply },
      { quoted: msg }
    );
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

start().catch((err) => {
  logger.error(err, 'WhatsApp bridge failed to start');
  process.exit(1);
});
