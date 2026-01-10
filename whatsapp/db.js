const fs = require('fs');
const path = require('path');
const Database = require('better-sqlite3');

const dataDir = path.join(__dirname, 'data');
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}
const userDbPath = path.join(dataDir, 'users.sqlite');
const userDb = new Database(userDbPath);

function initUserDb() {
  userDb.pragma('journal_mode = wal');
  userDb.prepare(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      salt TEXT NOT NULL,
      created_at INTEGER NOT NULL
    );
  `).run();
}

initUserDb();

const crypto = require('crypto');

function hashPassword(password, salt) {
  const derived = crypto.scryptSync(password, salt, 64).toString('hex');
  return `${salt}:${derived}`;
}

function verifyPassword(password, stored) {
  const [salt, digest] = stored.split(':');
  if (!salt || !digest) return false;
  const derived = hashPassword(password, salt).split(':')[1];
  return crypto.timingSafeEqual(Buffer.from(digest, 'hex'), Buffer.from(derived, 'hex'));
}

function createUser(username, password) {
  const salt = require('crypto').randomBytes(16).toString('hex');
  const password_hash = hashPassword(password, salt);
  const now = Date.now();
  const stmt = userDb.prepare('INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)');
  stmt.run(username, password_hash, salt, now);
  return { username };
}

function getUser(username) {
  return userDb.prepare('SELECT * FROM users WHERE username = ?').get(username);
}

function hasUsers() {
  const row = userDb.prepare('SELECT COUNT(1) as cnt FROM users').get();
  return row?.cnt > 0;
}

function listUsers() {
  return userDb.prepare('SELECT username, created_at as createdAt FROM users ORDER BY created_at DESC').all();
}

function ensureDefaultUser() {
  if (hasUsers()) return null;
  return createUser('admin', 'admin');
}

const storeCache = new Map();

function getStore(account) {
  const key = account || 'default';
  if (storeCache.has(key)) return storeCache.get(key);

  const safe = key.replace(/[^a-zA-Z0-9_-]/g, '_');
  const accDir = path.join(dataDir, safe);
  if (!fs.existsSync(accDir)) fs.mkdirSync(accDir, { recursive: true });
  const accDbPath = path.join(accDir, 'db.sqlite');
  const accDb = new Database(accDbPath);
  try {
    accDb.pragma('journal_mode = wal');
    accDb.pragma('synchronous = normal');
  } catch (err) {
    console.warn('SQLite pragma setup failed', err);
  }

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
      accDb.prepare(trimmed).run();
    }
  });

  try { accDb.prepare('ALTER TABLE chats ADD COLUMN muted INTEGER DEFAULT 0').run(); } catch (e) { /* ignore */ }

  const upsertChatStmt = accDb.prepare(
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

  const insertMessageStmt = accDb.prepare(
    `INSERT INTO messages (jid, from_me, text, ts, key_id)
     VALUES (@jid, @from_me, @text, @ts, @key_id)`
  );

  const listChatsStmt = accDb.prepare(
    `SELECT jid, name, is_group as isGroup, last_message as lastMessage, last_ts as lastTs, unread, muted
     FROM chats
     ORDER BY (last_ts IS NULL), last_ts DESC
     LIMIT ? OFFSET ?`
  );

  const getMessagesStmt = accDb.prepare(
    `SELECT id, jid, from_me as fromMe, text, ts, key_id as keyId
     FROM messages
     WHERE jid = ?
     ORDER BY ts DESC
     LIMIT ? OFFSET ?`
  );

  const getChatStmt = accDb.prepare(
    `SELECT jid, name, is_group as isGroup, last_message as lastMessage, last_ts as lastTs, unread, muted
     FROM chats WHERE jid = ?`
  );

  function saveMessage({ jid, fromMe, text, ts, keyId, name, isGroup }) {
    const safeTs = ts || Date.now();
    const existing = getChatStmt.get(jid);
    const unreadCount = fromMe ? 0 : ((existing?.unread || 0) + 1);
    const muted = existing?.muted ?? 0;

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
      accDb.prepare('UPDATE chats SET muted = ? WHERE jid = ?').run(muted ? 1 : 0, jid);
    }
  }

  const store = {
    saveMessage,
    listChats,
    getMessages,
    getChat,
    setMuted,
    dbPath: accDbPath,
  };

  storeCache.set(key, store);
  return store;
}

module.exports = {
  getStore,
  userStore: {
    createUser,
    getUser,
    verifyPassword,
    hasUsers,
    listUsers,
    ensureDefaultUser,
  },
  dataDir,
};
