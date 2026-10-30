"""SQLite connection handling and schema initialisation."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# Owns the searches saved before accounts existed. It has no login, and guests no longer write rows.
GUEST_USER_ID = 1

# Columns added to `users` after the first release; CREATE TABLE IF NOT EXISTS won't add them.
_USER_MIGRATIONS = {
    "password_hash": "TEXT",
    "session_id": "TEXT",
    "login_timestamp": "TEXT",
    "session_time": "INTEGER",
}


@contextmanager
def connect(db_path: str) -> Iterator[sqlite3.Connection]:
    """Open a short-lived connection; commits on success, rolls back on error."""
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_users(conn: sqlite3.Connection) -> None:
    """Add any user columns missing from an older database, then the session index."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    for column, column_type in _USER_MIGRATIONS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE users ADD COLUMN {column} {column_type}")
    # Created here, not in schema.sql, because session_id may not exist until the loop above runs.
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_session ON users(session_id)")


def init_db(db_path: str) -> None:
    """Create the database file and tables if needed, and seed the guest user."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _migrate_users(conn)
        conn.execute(
            "INSERT OR IGNORE INTO users (id, display_name) VALUES (?, ?)",
            (GUEST_USER_ID, "Guest"),
        )


if __name__ == "__main__":
    from app.config import get_settings

    path = get_settings().database_path
    init_db(path)
    print(f"Database ready at {path}")
