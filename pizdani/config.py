import os, sys
import pathlib
import tempfile

CACHE_DIR = pathlib.Path(os.environ.get("CACHE_DIR", tempfile.gettempdir()))


TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_URL_BASE = "https://api.telegram.org"
TG_URL_TEMPLATE = "{base}/bot{token}/{method}"

SS_COMMAND = os.environ.get("SS_COMMAND", "wine balcon.exe -n Nicolai")

# Inline mode needs a chat to upload files to, as inline messages only accept file_ids.
INLINE_STORAGE_CHAT = os.environ.get("INLINE_STORAGE_CHAT")
# Comma separated user ids allowed to use inline mode, empty means everyone.
INLINE_USERS = {int(i) for i in os.environ.get("INLINE_USERS", "").split(",") if i}
