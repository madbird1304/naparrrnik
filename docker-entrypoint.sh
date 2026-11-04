#!/bin/sh
# The voice engine needs a window (hangs without X) and a sound device (without
# one it produces different audio), even though it only writes to a file.
set -e
mkdir -p "$CACHE_DIR/ss"
Xvfb "$DISPLAY" -screen 0 1024x768x24 -nolisten tcp >/dev/null 2>&1 &
sleep 1
exec "$@"
