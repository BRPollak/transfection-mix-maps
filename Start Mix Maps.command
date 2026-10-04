#!/bin/zsh
set -eu
cd -- "$(dirname -- "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ -x .venv/bin/python ]] && .venv/bin/python -c 'import streamlit, pandas, openpyxl, gspread' >/dev/null 2>&1; then
  exec .venv/bin/python launch.py
fi
if ! command -v uv >/dev/null 2>&1; then
  print 'This app needs uv for its first setup. Install it from https://docs.astral.sh/uv/getting-started/installation/ and reopen this launcher.'
  read '?Press Return to close.'
  exit 1
fi
export UV_CACHE_DIR="$PWD/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.python"
if ! uv sync --locked --no-dev --python 3.12; then
  print 'Setup did not finish. Check the message above and your internet connection.'
  read '?Press Return to close.'
  exit 1
fi
exec .venv/bin/python launch.py
