const fs = require('fs');
const path = require('path');
const Database = require('better-sqlite3');

const dataDir = path.join(__dirname, 'data');
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}
const dbPath = path.join(dataDir, 'db.sqlite');
const db = new Database(dbPath);

// Improve durability for concurrent writes
try {
  db.pragma('journal_mode = wal');
  db.pragma('synchronous = normal');
} catch (err) {
  // Best effort; log to console since logger is in index.js
  console.warn('SQLite pragma setup failed', err);
}

// Schema
const createTables = `
CREATE TABLE IF NOT EXISTS chats (
  jid TEXT PRIMARY KEY,
  name TEXT,
  is_group INTEGER DEFAULT 0,
  last_message TEXT,
  last_ts INTEGER,
  unread INTEGER DEFAULT 0,
  muted INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  jid TEXT NOT NULL,
  from_me INTEGER DEFAULT 0,
  text TEXT,
  ts INTEGER,
  key_id TEXT
);
`;

createTables.split(';').forEach((stmt) => {
  const trimmed = stmt.trim();
  if (trimmed) {
    db.prepare(trimmed).run();
  }
});

// Best-effort migration for muted column
try { db.prepare('ALTER TABLE chats ADD COLUMN muted INTEGER DEFAULT 0').run(); } catch (e) { /* ignore */ }

const upsertChatStmt = db.prepare(
  `INSERT INTO chats (jid, name, is_group, last_message, last_ts, unread, muted)
   VALUES (@jid, @name, @is_group, @last_message, @last_ts, @unread, @muted)
   ON CONFLICT(jid) DO UPDATE SET
     name=COALESCE(excluded.name, chats.name),
     is_group=excluded.is_group,
     last_message=excluded.last_message,
     last_ts=excluded.last_ts,
     unread=excluded.unread,
     muted=COALESCE(excluded.muted, chats.muted)`
);

const insertMessageStmt = db.prepare(
  `INSERT INTO messages (jid, from_me, text, ts, key_id)
   VALUES (@jid, @from_me, @text, @ts, @key_id)`
);

const listChatsStmt = db.prepare(
  `SELECT jid, name, is_group as isGroup, last_message as lastMessage, last_ts as lastTs, unread, muted
   FROM chats
   ORDER BY (last_ts IS NULL), last_ts DESC
   LIMIT ? OFFSET ?`
);

const getMessagesStmt = db.prepare(
  `SELECT id, jid, from_me as fromMe, text, ts, key_id as keyId
   FROM messages
   WHERE jid = ?
   ORDER BY ts DESC
   LIMIT ? OFFSET ?`
);

const getChatStmt = db.prepare(
  `SELECT jid, name, is_group as isGroup, last_message as lastMessage, last_ts as lastTs, unread, muted
   FROM chats WHERE jid = ?`
);

function saveMessage({ jid, fromMe, text, ts, keyId, name, isGroup }) {
  const safeTs = ts || Date.now();
  const existing = getChatStmt.get(jid);
  const unreadCount = fromMe ? 0 : ((existing?.unread || 0) + 1);
  const muted = existing?.muted ?? 0;

  // Ensure chat row exists before inserting message
  upsertChatStmt.run({
    jid,
    name: name || null,
    is_group: isGroup ? 1 : 0,
    last_message: text || '',
    last_ts: safeTs,
    unread: unreadCount,
    muted,
  });

  insertMessageStmt.run({ jid, from_me: fromMe ? 1 : 0, text: text || '', ts: safeTs, key_id: keyId || null });
}

function listChats(limit = 50, offset = 0) {
  return listChatsStmt.all(limit, offset);
}

function getMessages(jid, limit = 50, offset = 0) {
  return getMessagesStmt.all(jid, limit, offset);
}

function getChat(jid) {
  return getChatStmt.get(jid);
}

function setMuted(jid, muted) {
  const existing = getChatStmt.get(jid);
  if (!existing) {
    upsertChatStmt.run({
      jid,
      name: null,
      is_group: 0,
      last_message: null,
      last_ts: null,
      unread: 0,
      muted: muted ? 1 : 0,
    });
  } else {
    db.prepare('UPDATE chats SET muted = ? WHERE jid = ?').run(muted ? 1 : 0, jid);
  }
}

module.exports = {
  saveMessage,
  listChats,
  getMessages,
  getChat,
  setMuted,
  dbPath,
};
