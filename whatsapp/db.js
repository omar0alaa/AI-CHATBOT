const fs = require('fs');
const path = require('path');
const Database = require('better-sqlite3');
const crypto = require('crypto');

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
  muted INTEGER DEFAULT 0,
  profile_pic TEXT,
  archived INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  jid TEXT NOT NULL,
  from_me INTEGER DEFAULT 0,
  text TEXT,
  ts INTEGER,
  key_id TEXT
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  salt TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
`;

createTables.split(';').forEach((stmt) => {
  const trimmed = stmt.trim();
  if (trimmed) {
    db.prepare(trimmed).run();
  }
});

// Best-effort migrations for new columns
try { db.prepare('ALTER TABLE chats ADD COLUMN muted INTEGER DEFAULT 0').run(); } catch (e) { /* ignore */ }
try { db.prepare('ALTER TABLE chats ADD COLUMN profile_pic TEXT').run(); } catch (e) { /* ignore */ }
try { db.prepare('ALTER TABLE chats ADD COLUMN archived INTEGER DEFAULT 0').run(); } catch (e) { /* ignore */ }

// User utilities
function hashPassword(password, salt) {
  const derived = crypto.scryptSync(password, salt, 64).toString('hex');
  return `${salt}:${derived}`;
}

function verifyPassword(password, stored) {
  const [salt, digest] = (stored || '').split(':');
  if (!salt || !digest) return false;
  const derived = hashPassword(password, salt).split(':')[1];
  return crypto.timingSafeEqual(Buffer.from(digest, 'hex'), Buffer.from(derived, 'hex'));
}

function createUser(username, password) {
  const salt = crypto.randomBytes(16).toString('hex');
  const password_hash = hashPassword(password, salt);
  const now = Date.now();
  db.prepare('INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)')
    .run(username, password_hash, salt, now);
  return { username };
}

function getUser(username) {
  return db.prepare('SELECT * FROM users WHERE username = ?').get(username);
}

function hasUsers() {
  const row = db.prepare('SELECT COUNT(1) as cnt FROM users').get();
  return row?.cnt > 0;
}

function listUsers() {
  return db.prepare('SELECT username, created_at as createdAt FROM users ORDER BY created_at DESC').all();
}

function ensureDefaultUser() {
  if (hasUsers()) return null;
  return createUser('admin', 'admin');
}

const upsertChatStmt = db.prepare(
    `INSERT INTO chats (jid, name, is_group, last_message, last_ts, unread, muted, profile_pic, archived)
     VALUES (@jid, @name, @is_group, @last_message, @last_ts, @unread, @muted, @profile_pic, @archived)
     ON CONFLICT(jid) DO UPDATE SET
       name=COALESCE(chats.name, excluded.name),
       is_group=excluded.is_group,
       last_message=excluded.last_message,
       last_ts=excluded.last_ts,
       unread=excluded.unread,
       muted=COALESCE(excluded.muted, chats.muted),
       profile_pic=COALESCE(excluded.profile_pic, chats.profile_pic),
       archived=COALESCE(excluded.archived, chats.archived)`
);

const insertMessageStmt = db.prepare(
  `INSERT INTO messages (jid, from_me, text, ts, key_id)
   VALUES (@jid, @from_me, @text, @ts, @key_id)`
);

const listChatsStmt = db.prepare(
  `SELECT jid, name, is_group as isGroup, last_message as lastMessage, last_ts as lastTs, unread, muted, profile_pic as profilePic, archived
   FROM chats
   WHERE COALESCE(archived, 0) = 0
   ORDER BY (last_ts IS NULL), last_ts DESC
   LIMIT ? OFFSET ?`
);

const listChatsAllStmt = db.prepare(
  `SELECT jid, name, is_group as isGroup, last_message as lastMessage, last_ts as lastTs, unread, muted, profile_pic as profilePic, archived
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
  `SELECT jid, name, is_group as isGroup, last_message as lastMessage, last_ts as lastTs, unread, muted, profile_pic as profilePic, archived
   FROM chats WHERE jid = ?`
);

function saveMessage({ jid, fromMe, text, ts, keyId, name, isGroup }) {
  const safeTs = ts || Date.now();
  const existing = getChatStmt.get(jid);
  const unreadCount = fromMe ? 0 : ((existing?.unread || 0) + 1);
  const muted = existing?.muted ?? 0;
  const profilePic = existing?.profilePic || null;
  const archived = existing?.archived || 0;

  // Ensure chat row exists before inserting message
  upsertChatStmt.run({
    jid,
    name: name || null,
    is_group: isGroup ? 1 : 0,
    last_message: text || '',
    last_ts: safeTs,
    unread: unreadCount,
    muted,
    profile_pic: profilePic,
    archived,
  });

  insertMessageStmt.run({ jid, from_me: fromMe ? 1 : 0, text: text || '', ts: safeTs, key_id: keyId || null });
}

function listChats(limit = 50, offset = 0, includeArchived = false) {
  return includeArchived ? listChatsAllStmt.all(limit, offset) : listChatsStmt.all(limit, offset);
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
      profile_pic: null,
      archived: 0,
    });
  } else {
    db.prepare('UPDATE chats SET muted = ? WHERE jid = ?').run(muted ? 1 : 0, jid);
  }
}

function setProfilePic(jid, profilePic) {
  db.prepare('UPDATE chats SET profile_pic = ? WHERE jid = ?').run(profilePic, jid);
}

function archiveChat(jid, archived = true) {
  db.prepare('UPDATE chats SET archived = ? WHERE jid = ?').run(archived ? 1 : 0, jid);
}

function deleteChat(jid) {
  db.prepare('DELETE FROM messages WHERE jid = ?').run(jid);
  db.prepare('DELETE FROM chats WHERE jid = ?').run(jid);
}

function upsertChatMeta({ jid, name = null, isGroup = false, lastMessage = null, lastTs = null, unread = 0, muted = 0, profilePic = null, archived = 0 }) {
  if (!jid) return;
  upsertChatStmt.run({
    jid,
    name,
    is_group: isGroup ? 1 : 0,
    last_message: lastMessage,
    last_ts: lastTs,
    unread: unread || 0,
    muted: muted ? 1 : 0,
    profile_pic: profilePic,
    archived: archived ? 1 : 0,
  });
}

module.exports = {
  saveMessage,
  listChats,
  getMessages,
  getChat,
  setMuted,
  setProfilePic,
  archiveChat,
  deleteChat,
  upsertChatMeta,
  dbPath,
  userStore: {
    createUser,
    getUser,
    verifyPassword,
    hasUsers,
    listUsers,
    ensureDefaultUser,
  },
};
