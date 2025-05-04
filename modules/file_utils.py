import os
import json
import hashlib
import sqlite3
import subprocess
import shutil
import logging

logger = logging.getLogger(__name__)


def write_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write JSON to {filepath}: {e}")


def read_json(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}


def calculate_sha256(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def get_local_file_duration(filepath):
    if not os.path.exists(filepath):
        return 0.0
    ffprobe_path = os.getenv("FFPROBE_PATH", "ffprobe")
    if not shutil.which(ffprobe_path):
        logger.error("ffprobe not found. Returning duration=0.")
        return 0.0

    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        filepath,
    ]
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True
        )
        return float(result.stdout.strip())
    except Exception:
        logger.error("Failed to get duration from ffprobe.")
        return 0.0


def print_progress_bar(
    iteration, total, prefix="", suffix="", decimals=1, length=50, fill="█"
):
    percent = f"{100 * (iteration / float(total)):.{decimals}f}"
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + "-" * (length - filled_length)
    print(f"\r{prefix} |{bar}| {percent}% {suffix}", end="", flush=True)
    if iteration == total:
        print()


def process_chat_to_sqlite(chat_json_path, sqlite_path):
    if not os.path.exists(chat_json_path):
        logger.warning(f"Chat JSON file not found: {chat_json_path}")
        return

    with open(chat_json_path, "r", encoding="utf-8") as f:
        try:
            chat_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load chat JSON {chat_json_path}: {e}")
            return

    comments = chat_data.get("comments", [])
    total_comments = len(comments)

    os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            message_id TEXT PRIMARY KEY,
            message_sent_absolute TEXT,
            message_sent_offset REAL,
            user_name TEXT,
            user_id TEXT,
            user_logo TEXT,
            message_body TEXT,
            bits INTEGER,
            color TEXT
        )
    """
    )

    c.execute("CREATE INDEX IF NOT EXISTS idx_user_name ON chat_messages (user_name)")
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_message_body ON chat_messages (message_body)"
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_message_sent_offset ON chat_messages (message_sent_offset)"
    )

    from .file_utils import print_progress_bar

    for i, comment in enumerate(comments, start=1):
        message_id = comment.get("_id", f"msg_{i}")
        created_at = comment.get("created_at", "")
        offset = comment.get("content_offset_seconds", 0.0)
        commenter = comment.get("commenter", {})
        user_name = commenter.get("display_name", "UnknownUser")
        user_id = commenter.get("_id", "")
        user_logo = commenter.get("logo", "")
        message = comment.get("message", {})
        message_body = message.get("body", "")
        bits_spent = message.get("bits_spent", 0)
        user_color = message.get("user_color", "#FFFFFF")

        c.execute(
            """
            INSERT OR REPLACE INTO chat_messages (
                message_id, message_sent_absolute, message_sent_offset,
                user_name, user_id, user_logo, message_body, bits, color
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                message_id,
                created_at,
                offset,
                user_name,
                user_id,
                user_logo,
                message_body,
                bits_spent,
                user_color,
            ),
        )
        print_progress_bar(
            i, total_comments, prefix="Inserting Chat", suffix="Complete"
        )

    conn.commit()
    conn.close()


def init_live_chat_sqlite(sqlite_path):
    os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_sent_absolute TEXT,
            user_name TEXT,
            message_body TEXT,
            bits INTEGER,
            user_color TEXT,
            raw_json TEXT
        )
    """
    )

    c.execute("CREATE INDEX IF NOT EXISTS idx_user_name ON chat_messages (user_name)")
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_message_body ON chat_messages (message_body)"
    )
    conn.commit()
    conn.close()


def insert_chat_message_sqlite(sqlite_path, msg_dict):
    import json

    conn = sqlite3.connect(sqlite_path)
    c = conn.cursor()

    message_sent = msg_dict.get("time_text", "")
    user_name = msg_dict.get("author", {}).get("name", "UnknownUser")
    message_body = msg_dict.get("message", "")
    bits_spent = msg_dict.get("bits", 0)
    user_color = msg_dict.get("author", {}).get("color", "#FFFFFF")

    raw_str = json.dumps(msg_dict, ensure_ascii=False)

    c.execute(
        """
        INSERT INTO chat_messages (
            message_sent_absolute,
            user_name,
            message_body,
            bits,
            user_color,
            raw_json
        ) VALUES (?, ?, ?, ?, ?, ?)
    """,
        (message_sent, user_name, message_body, bits_spent, user_color, raw_str),
    )
    conn.commit()
    conn.close()
