import os
import json
from datetime import datetime, timezone
from twitchio.ext import commands


class ChatLogger(commands.Bot):
    def __init__(
        self,
        token,
        channel_name,
        stream_folder,
        initial_meta,
        chat_log_filename="chat.undetermined.log",
        *,
        loop=None,
    ):
        """
        :param token: OAuth token to authenticate with Twitch (e.g., 'oauth:abcd1234')
        :param channel_name: The name of the Twitch channel to join, e.g. "SomeStreamer"
        :param stream_folder: Local path where logs and metadata for this stream session are stored
        :param initial_meta: A dict of existing metadata for the stream (e.g., from metadata.json)
        :param chat_log_filename: Filename for logging chat messages (default is "chat.live.log")
        :param loop: Optional event loop if you’re integrating with an existing asyncio loop
        """
        super().__init__(
            token=token, prefix="!", initial_channels=[channel_name], loop=loop
        )
        self.stream_folder = stream_folder

        self.chat_file = os.path.join(stream_folder, chat_log_filename)
        os.makedirs(stream_folder, exist_ok=True)

        self.metadata_path = os.path.join(stream_folder, "metadata.json")
        self.metadata = initial_meta or {}
        if "start_time" in self.metadata:
            self.stream_start_time = datetime.fromisoformat(self.metadata["start_time"])
        else:
            self.stream_start_time = datetime.now(timezone.utc)

    async def event_ready(self):
        print(f"[ChatLogger] Logged in as {self.nick}")

    async def event_message(self, message):
        now_utc = datetime.now(timezone.utc)
        abs_str = now_utc.isoformat()
        delta = now_utc - self.stream_start_time
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        rel_str = f"{h:02d}:{m:02d}:{s:02d}"
        author_name = message.author.name if message.author else "UnknownUser"
        bits = 0
        if message.tags and "bits" in message.tags:
            try:
                bits = int(message.tags["bits"])
            except ValueError:
                bits = 0
        raw_color = message.tags.get("color", "") if message.tags else ""
        color_3 = ""
        if raw_color.startswith("#") and len(raw_color) == 7:
            compressed = raw_color[1::2]
            color_3 = f"#{compressed.upper()}"
        elif raw_color.startswith("#"):
            color_3 = raw_color
        roles = []
        if getattr(message.author, "is_mod", False):
            roles.append("MOD")
        if getattr(message.author, "is_vip", False):
            roles.append("VIP")
        if getattr(message.author, "is_subscriber", False):
            roles.append("SUB")
        if getattr(message.author, "is_broadcaster", False):
            roles.append("BROADCASTER")
        roles_str = " ".join(roles) if roles else "None"
        stickers = []
        if message.tags and "emotes" in message.tags:
            emote_data = message.tags["emotes"]
            if emote_data:
                for group in emote_data.split("/"):
                    parts = group.split(":")
                    if len(parts) == 2:
                        emote_id, _ranges = parts
                        stickers.append(
                            f"https://static-cdn.jtvnw.net/emoticons/v1/{emote_id}/3.0"
                        )
        extras = []
        if bits > 0:
            extras.append(f"bits={bits}")
        if color_3:
            extras.append(f"color={color_3}")
        if roles_str and roles_str != "None":
            extras.append(f"roles={roles_str}")
        if stickers:
            extras.append(f"stickers={stickers}")
        extras_str = ""
        if extras:
            extras_str = f" ({', '.join(extras)})"
        entry = (
            f"[{abs_str}] "
            f"[{rel_str}] "
            f"<{author_name}>"
            f"{extras_str} "
            f"{message.content}\n"
        )
        with open(self.chat_file, "a", encoding="utf-8", buffering=1) as f:
            f.write(entry)

    def update_title(self, new_title):
        change = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "new_title": new_title,
        }
        self.metadata.setdefault("title_changes", []).append(change)
        self.save_metadata()

    def save_metadata(self):
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2)
