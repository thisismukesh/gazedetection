#!/bin/bash
# Double-click to start Look Away. The first launch installs what it needs (about a minute).
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

pause() { read -n 1 -s -r -p "Press any key to close this window"; echo; }

if ! command -v uv >/dev/null 2>&1; then
  echo "Look Away needs 'uv' (https://docs.astral.sh/uv/). Install it, then double-click again."
  pause
  exit 1
fi

echo "Starting Look Away... the heads will open in your browser."
echo "Quit with Ctrl-C or by closing this window."
echo
uv run lookaway run "$@"
status=$?
echo
if [ "$status" -ne 0 ]; then
  echo "Look Away stopped with an error (code $status). The message above says why."
  echo "If the camera was refused: System Settings > Privacy & Security > Camera > allow Terminal."
fi
pause
exit "$status"
