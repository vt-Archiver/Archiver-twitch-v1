import os
import sys
import logging

from dotenv import load_dotenv

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("download_vods")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(
    os.path.join(LOG_DIR, "download_vods.log"), mode="a", encoding="utf-8"
)
file_handler.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s - %(message)s", "%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

try:
    from modules.api_utils import get_channel_id, get_vods_for_channel
    from modules.db_utils import init_db, upsert_stream_record
    from modules.file_utils import (
        read_json,
        write_json,
        calculate_sha256,
        get_local_file_duration,
    )
    from modules.video_utils import download_vod, download_thumbnail
except ImportError as e:
    logger.exception("Failed to import modules:")
    raise

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PERSONS_DIR = os.path.join(BASE_DIR, "persons")


def process_vod(channel_name, vod):
    logger.debug(f"[{channel_name}] process_vod called with VOD: {vod.get('id')}")

    vod_id = vod["id"]
    real_stream_id = vod.get("stream_id") or vod_id
    vod_title = vod["title"]
    duration_str = vod.get("duration", "")
    created_at = vod.get("created_at")
    thumbnail_url = vod.get("thumbnail_url")
    vod_url = vod.get("url")

    safe_title = "".join(
        c if c.isalnum() or c in (" ", "_", "-") else "_" for c in vod_title
    )
    folder_name = os.path.join(
        PERSONS_DIR,
        channel_name,
        "twitch",
        "livestreams",
        f"{safe_title}_{real_stream_id}",
    )
    os.makedirs(folder_name, exist_ok=True)
    videos_dir = os.path.join(folder_name, "videos")
    os.makedirs(videos_dir, exist_ok=True)

    vod_file = os.path.join(videos_dir, "vod.mp4")
    thumb_dir = os.path.join(folder_name, "thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)
    thumb_file = os.path.join(thumb_dir, "vod_thumbnail.jpg")
    metadata_file = os.path.join(folder_name, "metadata.json")

    logger.info(f"[{channel_name}] Processing VOD id={vod_id}, folder={folder_name}")

    existing_meta = read_json(metadata_file)

    if os.path.exists(vod_file):
        logger.info(f"[{channel_name}] VOD file already exists: {vod_file}")
        local_duration = get_local_file_duration(vod_file)
        logger.debug(
            f"[{channel_name}] local_duration={local_duration:.1f}s, twitch_duration_str={duration_str}"
        )
    else:
        logger.debug(f"[{channel_name}] Downloading VOD from {vod_url}")
        try:
            download_vod(vod_url, vod_file)
        except Exception as e:
            logger.exception(f"[{channel_name}] Error downloading VOD {vod_id}")
            return

    if thumbnail_url and not os.path.exists(thumb_file):
        logger.debug(f"[{channel_name}] Downloading thumbnail {thumbnail_url}")
        try:
            download_thumbnail(thumbnail_url, thumb_file)
        except Exception as e:
            logger.exception(f"[{channel_name}] Error downloading thumbnail:")

    if os.path.exists(vod_file) and "vod_sha256" not in existing_meta:
        logger.debug(f"[{channel_name}] Computing SHA256 for {vod_file}")
        sha = calculate_sha256(vod_file)
        existing_meta["vod_sha256"] = sha

    existing_meta.update(
        {
            "stream_id": real_stream_id,
            "vod_id": vod_id,
            "title": vod_title,
            "thumbnail_url": thumbnail_url,
            "url": vod_url,
        }
    )
    write_json(metadata_file, existing_meta)

    try:
        upsert_stream_record(
            real_stream_id,
            channel_name,
            folder_name,
            existing_meta.get("start_time", created_at),
            existing_meta.get("end_time"),
            vod_title,
            source="vod",
        )
    except Exception as e:
        logger.exception(
            f"[{channel_name}] Failed upserting VOD info into DB for {vod_id}"
        )

    logger.info(f"[{channel_name}] Finished processing VOD id={vod_id}")


def process_channel(channel_name):
    logger.info(f"[{channel_name}] process_channel started.")
    try:
        user_id = get_channel_id(channel_name)
    except Exception as e:
        logger.exception(f"[{channel_name}] Error looking up channel_id")
        return
    if not user_id:
        logger.error(
            f"[{channel_name}] Could not retrieve user_id. Channel may not exist."
        )
        return

    logger.debug(f"[{channel_name}] user_id={user_id}")

    all_vods = []
    cursor = None

    while True:
        try:
            data = get_vods_for_channel(user_id, cursor)
        except Exception as e:
            logger.exception(f"[{channel_name}] Error fetching VODs:")
            break

        vod_data = data.get("data", [])
        if not vod_data:
            logger.info(f"[{channel_name}] No more VODs returned. Stopping pagination.")
            break

        all_vods.extend(vod_data)
        cursor = data.get("pagination", {}).get("cursor")
        if not cursor:
            logger.debug(f"[{channel_name}] No pagination cursor left.")
            break

    logger.info(f"[{channel_name}] Found {len(all_vods)} total VODs.")

    for vod in all_vods:
        try:
            process_vod(channel_name, vod)
        except Exception as e:
            logger.exception(f"[{channel_name}] Exception processing a VOD:")


def main():
    logger.info("download_vods.py started.")
    try:
        init_db()
    except Exception as e:
        logger.exception("Failed to init DB. Exiting.")
        return

    channel_str = os.getenv("CHANNEL_NAMES", "")
    channels = [c.strip() for c in channel_str.split(",") if c.strip()]

    logger.debug(f"Channels from .env: {channels}")

    if not channels:
        logger.warning("No CHANNEL_NAMES found in .env. Exiting.")
        return

    for ch in channels:
        process_channel(ch)

    logger.info("download_vods.py finished. Exiting normally.")


if __name__ == "__main__":
    main()
