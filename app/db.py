import sqlite3
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BANKING_DB_PATH = str(PROJECT_ROOT / "banking.db")
AGENT_DB_PATH = str(PROJECT_ROOT / "agent.db")

def init_dbs():
    schemas = [
        (BANKING_DB_PATH, PROJECT_ROOT / "schema" / "banking.sql"),
        (AGENT_DB_PATH, PROJECT_ROOT / "schema" / "agent.sql"),
    ]
    for db_path, schema_file in schemas:
        with sqlite3.connect(db_path) as conn:
            with schema_file.open("r", encoding="utf-8") as schema:
                conn.executescript(schema.read())

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