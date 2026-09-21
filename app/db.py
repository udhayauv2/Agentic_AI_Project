import sqlite3
import os
from contextlib import contextmanager

BANKING_DB_PATH = "banking.db"
AGENT_DB_PATH = "agent.db"

def init_dbs():
    for db_path, schema_file in [(BANKING_DB_PATH, "schema/banking.sql"), (AGENT_DB_PATH, "schema/agent.sql")]:
        with sqlite3.connect(db_path) as conn:
            if os.path.exists(schema_file):
                with open(schema_file, "r", encoding="utf-8") as f:
                    conn.executescript(f.read())

@contextmanager
def get_banking_conn():
    conn = sqlite3.connect(BANKING_DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

@contextmanager
def get_agent_conn():
    conn = sqlite3.connect(AGENT_DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()