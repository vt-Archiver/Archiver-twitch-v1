import os
import subprocess
import re
import logging
import shutil
from tqdm import tqdm

logger = logging.getLogger(__name__)


def record_live(channel_name, output_folder):
    videos_path = os.path.join(output_folder, "videos")
    os.makedirs(videos_path, exist_ok=True)
    out_path = os.path.join(videos_path, "live.mp4")

    env = os.environ.copy()
    env["TWITCH_OAUTH_TOKEN"] = os.getenv("ACCESS_TOKEN", "")

    cmd = [
        "streamlink",
        "--twitch-disable-ads",
        f"twitch.tv/{channel_name}",
        "best",
        "--stdout",
    ]

    logger.info(f"Recording live stream from {channel_name} -> {out_path}")
    logger.debug(f"Running streamlink command: {cmd}")

    process = subprocess.Popen(cmd, stdout=open(out_path, "wb"), env=env)
    return process


def download_vod(vod_url, vod_path):
    os.makedirs(os.path.dirname(vod_path), exist_ok=True)
    logger.info(f"Downloading VOD: {vod_url}")
    cmd = [
        "yt-dlp",
        "-f",
        "best",
        "--concurrent-fragments",
        "5",
        "--force-overwrites",
        "--newline",
        "-o",
        vod_path,
        vod_url,
    ]
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    progress_pattern = re.compile(r"\[download\]\s+([\d\.]+)%")
    pbar = tqdm(total=10000, desc="Downloading VOD", unit="0.01%", leave=True)
    last_progress = 0

    while True:
        line = process.stdout.readline()
        if not line:
            break
        match = progress_pattern.search(line)
        if match:
            progress_value = int(float(match.group(1)) * 100)
            if progress_value > last_progress:
                pbar.n = progress_value
                pbar.refresh()
                last_progress = progress_value
        else:
            logger.debug(line.strip())
    process.wait()
    pbar.close()

    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd)


def download_thumbnail(url, path):
    import requests

    os.makedirs(os.path.dirname(path), exist_ok=True)
    logger.info(f"Downloading thumbnail {url}")
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            with open(path, "wb") as f:
                f.write(r.content)
        else:
            logger.warning(f"Could not download thumbnail from {url}")
    except Exception as e:
        logger.error(f"Error downloading thumbnail: {e}")
