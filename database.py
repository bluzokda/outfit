import sqlite3
from contextlib import contextmanager

from config import config


def init_db() -> None:
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS wardrobe_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                photo_path TEXT NOT NULL,
                min_temp INTEGER,
                max_temp INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS outfit_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                occasion TEXT NOT NULL,
                city TEXT,
                temperature REAL,
                weather_condition TEXT,
                item_ids TEXT,
                collage_path TEXT,
                explanation TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_wardrobe_session ON wardrobe_items(session_id);
            CREATE INDEX IF NOT EXISTS idx_history_session ON outfit_history(session_id);
            """
        )


@contextmanager
def get_db():
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
