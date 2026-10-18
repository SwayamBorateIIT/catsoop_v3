#!/bin/sh
# Start the local demo deployment of this checkout (see demo/README.md).
# Uses its own config, so other CAT-SOOP configurations are not affected.
REPO="$(cd "$(dirname "$0")/.." && pwd)"
export CATSOOP_CONFIG="${CATSOOP_CONFIG:-$HOME/.config/catsoop-desktop/config.py}"
PYTHON="${CATSOOP_PYTHON:-$HOME/.venvs/catsoop-desktop/bin/python}"
cd "$REPO" && exec "$PYTHON" -m catsoop start "$@"
