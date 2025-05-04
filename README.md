# Archiver – Streamer backup toolkit  
*Version 1 of the Twitch Archiver. (A “v2” rewrite is in progress)*

The 'vt-Archiver' project is a self-hosted toolbox that automatically pulls down **livestreams, VODs, chat logs, thumbnails, and more** from your atached streamer and stores everything in an easy-to-query folder/database layout.
The extracted data can then be gotten via the companion **archive-website** or repackaged for long-term storage (e.g. Archive.org).

---

## Key features

| Feature | Script / module | Notes |
|---------|-----------------|-------|
| Record **live** streams while they are happening | `download_streams.py` → `video_utils.record_live()` (`streamlink`) | Captures video (`live.mp4`), periodic viewer counts & game / category changes (chapters) |
| Download **past VODs** in bulk | `download_vods.py` (uses `yt-dlp`) | Saves to `persons/<streamer>/twitch/livestreams/…` |
| **Log chat** in real-time | `chat_logger.py` (TwitchIO) | Emits colour, roles, bits & emote URLs; saves both line-delimited log & JSON |
| **Refresh OAuth tokens** on schedule | `refresh_env.py` | Validates / refreshes and rewrites your `.env` |
| **SQLite metadata DB** | `modules/db_utils.py` | Single table `streams` keeps high-level info; ideal for reporting |
| Pluggable helpers | `modules/*.py` (`api_utils`, `file_utils`, `video_utils`, …) | Re-usable utilities (SHA-256, ffprobe duration, progress bars, etc.) |

---

## Repository layout (abridged)

```
Archiver/
├─ archiver.scripts/
│  ├─ Archiver-twitch-v1      ← current version (v1)
│  │  ├─ .env
│  │  ├─ download\_streams.py
│  │  ├─ download\_vods.py
│  │  ├─ refresh\_env.py
│  │  ├─ modules/
│  │  └─ logs/
│  └─ youtube\_archiver/
├─ websites/                  ← location for storing the websites of said streamers
└─ persons/                   ← all fetched media ends up here
````

---

## ⚙️ Requirements

* **Python 3.11+** (the venv in `pyvenv.cfg` is on 3.12.8)  
* **ffmpeg/ffprobe** – binaries included in `.dependencies/ffmpeg/` (Windows) or available on PATH  
* **streamlink** 5.x  
* **yt-dlp** 2025.02+  
* **Twitch OAuth credentials** with scopes:  
`user:read:email user:read:broadcast channel:read:subscriptions chat:read chat:edit user_subscriptions`

All Python deps are pinned in `requirements.txt`.

---

## First-time setup

1. **Clone** the repo and create/activate a virtual-env:
```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
```

2. **Create `.env`** inside `archiver.scripts/twitch_archiver/`:
```ini
   CLIENT_ID=xxxxxxxxxxxx
   CLIENT_SECRET=xxxxxxxxxxxx
   ACCESS_TOKEN=…
   REFRESH_TOKEN=…
   REDIRECT_URI=http://localhost
   CHANNEL_NAMES=streamer1,streamer2
   CHECK_INTERVAL=300
   THUMB_INTERVAL=900
   FFPROBE_PATH=ffprobe
```
> Need help getting tokens?
> Follow `refresh_env.instruct.md` for a step-by-step guide (auth URL, scopes, curl exchange, etc.).

3. **(Optional) add binaries**
   Windows users can simply leave `ffprobe.exe`, `ffmpeg.exe`, `yt-dlp.exe` inside `.dependencies`.
   On Linux/macOS make sure they’re on `$PATH`.

---

## Usage

### Record the current live-stream (and chat)
```bash
cd archiver.scripts/twitch_archiver
python download_streams.py
```

*IMPORTANT NOTE:* This is using the old setup and I can't be bothered to migrate this version when I'll be remaking this for the v2 version.
It will therefore not integrate with the website section.

* A folder is created at `persons/<channel>/twitch/livestreams/<channel>_<timestamp>/`
  * `videos/live.mp4` – the stream
  * `chat.live.log` / `chat.live.json` – raw chat
  * `events.sqlite` – viewer & chapter info
  * `metadata.json` – everything else
* Real-time progress and debug information are printed to the console and appended to `logs/download_streams.log`.

### Bulk-download past VODs
```bash
python download_vods.py
```

* Iterates every VOD returned by the Helix API, skips files already present.
* Integrity checked via SHA-256, video duration verified via ffprobe.

### Keep tokens fresh

```bash
python refresh_env.py
```

* Validates the current `ACCESS_TOKEN` every 5 min (`CHECK_INTERVAL`).
* If expiry < 10 min it swaps in a new one using the stored `REFRESH_TOKEN`.
* Writes changes **back into `.env`** so other scripts pick them up automatically.

---

## Logs & debugging

All scripts write coloured console output **and** a timestamped file in `archiver.scripts/twitch_archiver/logs/`.
Adjust verbosity in `modules/logging_setup.py` (default: console = INFO, file = DEBUG).
