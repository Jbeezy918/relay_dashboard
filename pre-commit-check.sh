#!/usr/bin/env bash
set -euo pipefail
APP="/Users/joebudds/Documents/Updated_Relay_Files/app.py"

# Fail if duplicate "Section 5" shows up again
if grep -n "def enable_background_data_gathering_from_safe_sources" "$APP" | tail -n +2 | grep -q .; then
  echo "Duplicate Section 5 detected. Aborting commit." >&2
  exit 1
fi

# Ensure only one fromisoformat call remains
if [ "$(grep -c 'datetime.fromisoformat' "$APP")" -ne 1 ]; then
  echo "Unexpected direct datetime.fromisoformat calls detected." >&2
  exit 1
fi

python3 -m py_compile "$APP"

echo "✅ Pre-commit checks passed"