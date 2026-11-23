#!/bin/sh
# TSMod Save Editor launcher for Linux and Steam Deck (Desktop Mode).
#   sh TSModSaveEditor.sh            start the editor
#   sh TSModSaveEditor.sh --check    only report what was found
# Needs Python 3.11+ with Tk. SteamOS's own python3 has both (checked on a Steam Deck, 2026-11-22).
# No extra packages: the game's data is read with the editor's own pak reader (pure Python).
HERE="$(cd "$(dirname "$0")" && pwd)"
PY=""
for c in "$HERE/../../.venv/bin/python3" python3 python; do
  if command -v "$c" >/dev/null 2>&1 || [ -x "$c" ]; then
    if "$c" "$HERE/pycheck.py" >/dev/null 2>&1; then PY="$c"; break; fi
  fi
done
if [ "$1" = "--check" ]; then
  if [ -n "$PY" ]; then echo "Python: $("$PY" "$HERE/pycheck.py")"; else echo "Python: MISSING (3.11+ with Tk)"; fi
  exit 0
fi
if [ -z "$PY" ]; then
  msg="The TSMod Save Editor needs Python 3.11 or newer with Tk (tkinter). SteamOS includes it; on other Linux systems install your distribution's python3 and python3-tk packages."
  if command -v kdialog >/dev/null 2>&1; then kdialog --error "$msg"
  elif command -v zenity >/dev/null 2>&1; then zenity --error --text="$msg"
  else echo "$msg"; fi
  exit 1
fi
exec "$PY" "$HERE/TSModSaveEditor.pyw" "$@"
