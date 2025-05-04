import os
import requests
from dotenv import load_dotenv

TWITCH_STREAMS_ENDPOINT = "https://api.twitch.tv/helix/streams"
TWITCH_VIDEOS_ENDPOINT = "https://api.twitch.tv/helix/videos"
TWITCH_USERS_ENDPOINT = "https://api.twitch.tv/helix/users"


def get_headers():
    load_dotenv(override=True)
    client_id = os.getenv("CLIENT_ID")
    access_token = os.getenv("ACCESS_TOKEN")

    if not client_id or not access_token:
        raise RuntimeError("Missing CLIENT_ID or ACCESS_TOKEN in environment")

    return {"Client-ID": client_id, "Authorization": f"Bearer {access_token}"}


def get_stream_data(channel_name: str):
    headers = get_headers()
    params = {"user_login": channel_name}

    resp = requests.get(TWITCH_STREAMS_ENDPOINT, headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return data[0] if data else None


def get_channel_id(channel_name: str) -> str:
    headers = get_headers()
    params = {"login": channel_name}

    resp = requests.get(TWITCH_USERS_ENDPOINT, headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return data[0]["id"] if data else None


def get_vods_for_channel(user_id: str, after_cursor=None):
    headers = get_headers()
    params = {"user_id": user_id, "first": 100, "type": "archive"}
    if after_cursor:
        params["after"] = after_cursor

    resp = requests.get(TWITCH_VIDEOS_ENDPOINT, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()
