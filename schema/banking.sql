CREATE TABLE IF NOT EXISTS customer (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('customer', 'admin')),
    branch_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customer(id),
    balance REAL NOT NULL CHECK(balance >= 0.0),
    version INTEGER NOT NULL DEFAULT 0,
    is_frozen INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS transaction_log (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES account(id),
    amount REAL NOT NULL,
    action TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS idempotency (
    key TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    result TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed Data
INSERT OR IGNORE INTO customer VALUES ('CUST_1', 'Arjun Kumar', 'customer', 'BR_CHENNAI');
INSERT OR IGNORE INTO customer VALUES ('CUST_2', 'Priya Rao', 'customer', 'BR_CHENNAI');
INSERT OR IGNORE INTO customer VALUES ('ADMIN_1', 'Ramesh Iyer', 'admin', 'BR_CHENNAI');

INSERT OR IGNORE INTO account VALUES ('ACC_100', 'CUST_1', 15000.0, 0, 0);
INSERT OR IGNORE INTO account VALUES ('ACC_200', 'CUST_2', 3000.0, 0, 0);