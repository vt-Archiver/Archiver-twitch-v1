import os
import sqlite3
import logging

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "metadata", "database.db")

logger = logging.getLogger(__name__)


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute(
            """
        CREATE TABLE IF NOT EXISTS streams (
            stream_id TEXT PRIMARY KEY,
            channel_name TEXT,
            folder_name TEXT,
            start_time TEXT,
            end_time TEXT,
            title TEXT,
            source TEXT
        );
        """
        )
        conn.commit()


def upsert_stream_record(
    stream_id, channel_name, folder_name, start_time, end_time, title, source
):
    """
    Insert or update the record for a given stream_id in the 'streams' table.
    """
    try:
        with get_connection() as conn:
            c = conn.cursor()
            c.execute(
                """
            INSERT OR REPLACE INTO streams
                (stream_id, channel_name, folder_name, start_time, end_time, title, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    stream_id,
                    channel_name,
                    folder_name,
                    start_time,
                    end_time,
                    title,
                    source,
                ),
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to upsert record for {stream_id}: {e}")
