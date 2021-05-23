import os, sys
import pathlib
import tempfile

CACHE_DIR = pathlib.Path(os.environ.get("CACHE_DIR", tempfile.gettempdir()))


TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_URL_BASE = "https://api.telegram.org"
TG_URL_TEMPLATE = "{base}/bot{token}/{method}"

SS_COMMAND = os.environ.get("SS_COMMAND", "wine balcon.exe -n Nicolai")
