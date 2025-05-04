import os
import threading
import asyncio
import time
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
from modules.logging_setup import configure_logger
from modules.db_utils import upsert_stream_record
from modules.file_utils import (
    write_json,
    read_json,
    process_chat_to_sqlite,
    init_events_db,
    insert_viewer_event,
    insert_chapter_event,
)
from modules.video_utils import record_live
from modules.api_utils import get_stream_data
from chat_logger import ChatLogger

logger = configure_logger(
    logger_name="download_streams",
    log_file_name="download_streams.log",
    console_level=logging.DEBUG,
    file_level=logging.DEBUG,
)

load_dotenv(override=True)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def run_chat_logger(token, channel_name, folder, metadata):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot = ChatLogger(
        token,
        channel_name,
        folder,
        metadata,
        chat_json_filename="chat.live.json",
        loop=loop,
    )
    try:
        loop.run_until_complete(bot.start())
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


def monitor_viewer_chapters_sqlite(channel_name, folder, is_running_flag, interval=600):
    events_db = os.path.join(folder, "events.sqlite")
    init_events_db(events_db)

    last_game_name = None
    start_time = datetime.now(timezone.utc)

    while is_running_flag["value"]:
        now_utc = datetime.now(timezone.utc)
        elapsed_sec = (now_utc - start_time).total_seconds()

        try:
            stream_info = get_stream_data(channel_name)
            if stream_info:
                viewer_count = stream_info.get("viewer_count", 0)
                game_name = stream_info.get("game_name", "")

                insert_viewer_event(events_db, elapsed_sec, viewer_count)

                if game_name and game_name != last_game_name:
                    insert_chapter_event(events_db, elapsed_sec, game_name)
                    last_game_name = game_name
        except Exception as e:
            logger.exception(f"Error fetching viewer/game info for {channel_name}: {e}")

        for _ in range(interval):
            if not is_running_flag["value"]:
                break
            time.sleep(1)


def download_stream(channel_name, folder_name=None):
    logger.info(f"download_stream called for channel={channel_name}")

    if not folder_name:
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        folder_name = os.path.join(
            BASE_DIR,
            "persons",
            channel_name,
            "twitch",
            "livestreams",
            f"{channel_name}_{now_str}",
        )
    os.makedirs(folder_name, exist_ok=True)
    logger.debug(f"Folder for stream: {folder_name}")

    metadata_path = os.path.join(folder_name, "metadata.json")
    existing_meta = read_json(metadata_path)

    start_time_iso = datetime.now(timezone.utc).isoformat()
    existing_meta.update(
        {
            "stream_id": existing_meta.get("stream_id")
            or f"{channel_name}_{int(time.time())}",
            "vod_id": None,
            "title": existing_meta.get("title", f"Live Stream - {channel_name}"),
            "created_at": start_time_iso,
            "published_at": None,
            "thumbnail_url": None,
            "url": f"https://www.twitch.tv/{channel_name}",
            "downloaded_at": None,
            "vod_sha256": None,
            "duration": None,
            "duration_string": None,
            "start_time": start_time_iso,
            "end_time": None,
            "initial_title": existing_meta.get(
                "initial_title", f"Live: {channel_name}"
            ),
            "language": "en",
        }
    )
    write_json(metadata_path, existing_meta)

    try:
        upsert_stream_record(
            stream_id=existing_meta["stream_id"],
            channel_name=channel_name,
            folder_name=folder_name,
            start_time=existing_meta["start_time"],
            end_time=None,
            title=existing_meta["title"],
            source="live",
        )
    except Exception as e:
        logger.exception(f"DB error on upsert_stream_record: {e}")

    token = os.getenv("ACCESS_TOKEN", "")
    chat_thread = threading.Thread(
        target=run_chat_logger,
        args=(token, channel_name, folder_name, existing_meta),
        daemon=True,
    )
    chat_thread.start()

    is_running_flag = {"value": True}
    viewer_thread = threading.Thread(
        target=monitor_viewer_chapters_sqlite,
        args=(channel_name, folder_name, is_running_flag),
        daemon=True,
    )
    viewer_thread.start()

    from modules.video_utils import record_live
    import subprocess

    process = None
    try:
        process = record_live(channel_name, folder_name)
        logger.info(
            f"[{channel_name}] Recording started (PID={process.pid if process else 'N/A'})."
        )
        ret_code = process.wait()
        logger.info(f"[{channel_name}] Recording ended with code={ret_code}")
    except Exception as e:
        logger.exception(f"Error recording live stream for {channel_name}: {e}")
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait()

    is_running_flag["value"] = False

    end_time_iso = datetime.now(timezone.utc).isoformat()
    existing_meta["end_time"] = end_time_iso
    existing_meta["downloaded_at"] = end_time_iso

    from modules.file_utils import get_local_file_duration

    live_mp4 = os.path.join(folder_name, "videos", "live.mp4")
    dur_sec = get_local_file_duration(live_mp4)
    existing_meta["duration"] = int(dur_sec)
    h = int(dur_sec // 3600)
    m = int((dur_sec % 3600) // 60)
    s = int(dur_sec % 60)
    if h > 0:
        existing_meta["duration_string"] = f"{h}:{m:02d}:{s:02d}"
    else:
        existing_meta["duration_string"] = f"{m}:{s:02d}"

    write_json(metadata_path, existing_meta)

    try:
        upsert_stream_record(
            stream_id=existing_meta["stream_id"],
            channel_name=channel_name,
            folder_name=folder_name,
            start_time=existing_meta["start_time"],
            end_time=existing_meta["end_time"],
            title=existing_meta["title"],
            source="live",
        )
    except Exception as e:
        logger.exception(f"DB error final update: {e}")

    chat_json = os.path.join(folder_name, "chat.live.json")
    chat_sqlite = os.path.join(folder_name, "chat.live.sqlite")
    from modules.file_utils import process_chat_to_sqlite

    try:
        process_chat_to_sqlite(chat_json, chat_sqlite)
    except Exception as e:
        logger.exception(f"Error converting chat JSON to SQLite: {e}")

    logger.info(f"[{channel_name}] download_stream completed.")
