import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data.db"


def get_db_path() -> str:
    return os.environ.get("DATABASE_PATH", str(DEFAULT_DB_PATH))


@contextmanager
def connect():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


ITEMS_SCHEMA = """
    CREATE TABLE {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        text TEXT NOT NULL,
        done INTEGER NOT NULL DEFAULT 0,
        UNIQUE (user_id, text)
    )
"""


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _migrate_items_to_per_user(conn: sqlite3.Connection) -> None:
    """Stara tabela items (bez właściciela, tekst unikalny globalnie) -> zadania per konto.

    Istniejące zadania trafiają do najstarszego konta; bez kont zostają bez właściciela
    (niewidoczne dla nikogo).
    """
    conn.execute(ITEMS_SCHEMA.format(name="items_new"))
    conn.execute(
        """
        INSERT INTO items_new (id, user_id, text, done)
        SELECT id, (SELECT id FROM users ORDER BY id LIMIT 1), text, done FROM items
        """
    )
    conn.execute("DROP TABLE items")
    conn.execute("ALTER TABLE items_new RENAME TO items")


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        existing = _columns(conn, "items")
        if not existing:
            conn.execute(ITEMS_SCHEMA.format(name="items"))
        elif "user_id" not in existing:
            _migrate_items_to_per_user(conn)
