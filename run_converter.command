#!/bin/zsh
set -u

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3 and try again."
  echo
  read -k1 "?Press any key to close..."
  exit 1
fi

"$PYTHON_BIN" "$ROOT_DIR/scripts/convert_gpkg_to_kml.py"
EXIT_CODE=$?

echo
if [ $EXIT_CODE -eq 0 ]; then
  echo "Finished successfully."
  echo "You can now close this terminal window."
  exit 0
else
  echo "Finished with warnings/errors (exit code: $EXIT_CODE)."
  echo "You can now close this terminal window (or press any key)."
  echo
  read -k1 "?Press any key to close..."
  exit $EXIT_CODE
fi
