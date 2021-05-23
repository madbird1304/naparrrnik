import os, sys
import pathlib
import tempfile

from config import CACHE_DIR
# CACHE_DIR = pathlib.Path(os.environ.get("CACHE_DIR", tempfile.gettempdir()))

env = os.environ

# TG_TOKEN = os.environ["TOKEN"]
# TG_URL_BASE = "https://api.telegram.org"
# TG_URL_TEMPLATE = "{base}/bot{token}/{method}"

SS_BINARY = env.get(
    "SS_BINARY",
    "balcon.exe",
)
SS_COMMAND = env.get(
    "SS_COMMAND",
    "wine ${CMD} -n Nicolai -f ${INP} -w ${OUT}",
)

# SS_COMMAND = os.environ.get("SS_COMMAND") or );
SS_CACHE_DIR = env.get(
    "SS_CACHE_DIR",
    CACHE_DIR / "ss",
)
SS_CACHE_KEEP = __debug__
