import os
import time
import requests
import logging
from logging import FileHandler, StreamHandler, Formatter
from dotenv import load_dotenv, set_key

LOG_FILE = os.path.join(os.path.dirname(__file__), "logs/refresh_env.log")
logger = logging.getLogger("refresh_env")
logger.setLevel(logging.DEBUG)
file_handler = FileHandler(LOG_FILE, mode="a", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
console_handler = StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = Formatter("%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
REFRESH_URL = "https://id.twitch.tv/oauth2/token"
CHECK_INTERVAL = 300
REFRESH_THRESHOLD = 600
REQUIRED_SCOPES = ["chat:read", "chat:edit", "user_subscriptions"]


def load_env_vars():
    load_dotenv(ENV_FILE, override=True)
    env_data = {
        "CLIENT_ID": os.getenv("CLIENT_ID"),
        "CLIENT_SECRET": os.getenv("CLIENT_SECRET"),
        "ACCESS_TOKEN": os.getenv("ACCESS_TOKEN"),
        "REFRESH_TOKEN": os.getenv("REFRESH_TOKEN"),
        "AUTHORIZATION_CODE": os.getenv("AUTHORIZATION_CODE"),
        "REDIRECT_URI": os.getenv("REDIRECT_URI"),
    }
    return env_data


def validate_token(access_token, client_id):
    headers = {"Authorization": f"Bearer {access_token}", "Client-ID": client_id}
    try:
        resp = requests.get(VALIDATE_URL, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            logger.debug(f"Raw token validation response: {data}")
            logger.info(
                f"Token valid. Expires in {data.get('expires_in', '???')} sec. "
                f"Login: {data.get('login')}"
            )
            return data
        else:
            logger.warning(
                f"Token validation failed: HTTP {resp.status_code} - {resp.text}"
            )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error validating token: {e}")
    return None


def refresh_access_token(client_id, client_secret, refresh_token):
    logger.info("Refreshing access token via refresh_token...")
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    try:
        resp = requests.post(REFRESH_URL, data=data)
        if resp.status_code != 200:
            logger.warning(
                f"Refresh token request failed: HTTP {resp.status_code} - {resp.text}"
            )
            resp.raise_for_status()
        token_data = resp.json()
        new_access = token_data.get("access_token")
        new_refresh = token_data.get("refresh_token")

        if new_access:
            current_access = os.getenv("ACCESS_TOKEN")
            if new_access != current_access:
                set_key(ENV_FILE, "ACCESS_TOKEN", new_access)
                os.environ["ACCESS_TOKEN"] = new_access
        if new_refresh:
            current_refresh = os.getenv("REFRESH_TOKEN")
            if new_refresh != current_refresh:
                set_key(ENV_FILE, "REFRESH_TOKEN", new_refresh)
                os.environ["REFRESH_TOKEN"] = new_refresh

        logger.info("Successfully refreshed access token.")
        return token_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to refresh access token: {e}")
    return None


def initial_authorization(client_id, client_secret, authorization_code, redirect_uri):
    logger.info(
        "No refresh token found. Attempting initial authorization using AUTHORIZATION_CODE..."
    )
    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": authorization_code,
        "redirect_uri": redirect_uri,
    }
    try:
        resp = requests.post(REFRESH_URL, data=data)
        if resp.status_code != 200:
            logger.warning(
                f"Initial authorization failed: HTTP {resp.status_code} - {resp.text}"
            )
            resp.raise_for_status()
        token_data = resp.json()
        new_access = token_data.get("access_token")
        new_refresh = token_data.get("refresh_token")

        if new_access:
            set_key(ENV_FILE, "ACCESS_TOKEN", new_access)
            os.environ["ACCESS_TOKEN"] = new_access
        if new_refresh:
            set_key(ENV_FILE, "REFRESH_TOKEN", new_refresh)
            os.environ["REFRESH_TOKEN"] = new_refresh

        logger.info("Initial authorization successful. Tokens have been updated.")
        return token_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Initial authorization failed: {e}")
    return None


def log_scopes(token_data):
    token_scopes = token_data.get("scopes", [])
    logger.info(f"Token scopes: {', '.join(token_scopes) if token_scopes else 'None'}")
    missing_scopes = [
        scope for scope in REQUIRED_SCOPES if scope not in token_data.get("scopes", [])
    ]
    if missing_scopes:
        logger.warning(f"⚠️  Missing required scopes: {', '.join(missing_scopes)}")
    else:
        logger.info("✅ Token includes all required scopes.")


def main():
    env = load_env_vars()
    client_id = env["CLIENT_ID"]
    client_secret = env["CLIENT_SECRET"]
    access_token = env["ACCESS_TOKEN"]
    refresh_token = env["REFRESH_TOKEN"]
    authorization_code = env["AUTHORIZATION_CODE"]
    redirect_uri = env["REDIRECT_URI"]

    if not client_id or not client_secret:
        logger.critical("CLIENT_ID or CLIENT_SECRET missing. Exiting.")
        return

    if not refresh_token:
        if authorization_code and redirect_uri:
            logger.info("No refresh token found, but authorization code is available.")
            token_data = initial_authorization(
                client_id, client_secret, authorization_code, redirect_uri
            )
        else:
            logger.warning("No refresh token or AUTHORIZATION_CODE provided.")
            token_data = None
    else:
        if not access_token:
            logger.warning(
                "No ACCESS_TOKEN in .env. Attempting refresh via refresh token."
            )
            token_data = refresh_access_token(client_id, client_secret, refresh_token)
        else:
            token_data = validate_token(access_token, client_id)
            if not token_data or token_data.get("expires_in", 0) < REFRESH_THRESHOLD:
                logger.info("Token invalid or expiring soon. Refreshing...")
                token_data = refresh_access_token(
                    client_id, client_secret, refresh_token
                )
            else:
                logger.info("Initial token OK.")

    if token_data:
        log_scopes(token_data)
    else:
        logger.warning("No valid token data obtained on startup.")

    while True:
        time.sleep(CHECK_INTERVAL)
        env = load_env_vars()
        client_id = env["CLIENT_ID"]
        client_secret = env["CLIENT_SECRET"]
        access_token = env["ACCESS_TOKEN"]
        refresh_token = env["REFRESH_TOKEN"]

        if not access_token:
            logger.warning("ACCESS_TOKEN missing; attempting refresh anyway.")
            token_data = refresh_access_token(client_id, client_secret, refresh_token)
            continue

        token_data = validate_token(access_token, client_id)
        if not token_data:
            logger.info("Token invalid. Attempting refresh...")
            token_data = refresh_access_token(client_id, client_secret, refresh_token)
        else:
            expires_in = token_data.get("expires_in", 0)
            if expires_in < REFRESH_THRESHOLD:
                logger.info(f"Token expiring soon ({expires_in}s). Refreshing...")
                token_data = refresh_access_token(
                    client_id, client_secret, refresh_token
                )
            else:
                logger.info(f"Token OK. Next check in {CHECK_INTERVAL} seconds.")


if __name__ == "__main__":
    main()
