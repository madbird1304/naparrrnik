import pathlib
import os
import tempfile

CACHE_DIR = pathlib.Path(os.environ.get("CACHE_DIR", tempfile.gettempdir()))
