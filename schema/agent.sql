CREATE TABLE IF NOT EXISTS thread (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL REFERENCES thread(id),
    seq INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(thread_id, seq)
);

-- Append-only trigger: reject updates
CREATE TRIGGER IF NOT EXISTS abort_message_update
BEFORE UPDATE ON message
BEGIN
    SELECT RAISE(FAIL, 'Messages are append-only. UPDATE not permitted.');
END;

CREATE TABLE IF NOT EXISTS run (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES thread(id),
    status TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tool_call (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES run(id),
    tool_name TEXT NOT NULL,
    args TEXT NOT NULL,
    result TEXT NOT NULL
);