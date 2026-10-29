"""SQLite connection handling and schema initialisation."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# Single local user until OAuth login lands in the next iteration.
GUEST_USER_ID = 1


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


def init_db(db_path: str) -> None:
    """Create the database file and tables if needed, and seed the guest user."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT OR IGNORE INTO users (id, display_name) VALUES (?, ?)",
            (GUEST_USER_ID, "Guest"),
        )


if __name__ == "__main__":
    from app.config import get_settings

    path = get_settings().database_path
    init_db(path)
    print(f"Database ready at {path}")
