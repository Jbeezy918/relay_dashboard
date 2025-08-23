#!/bin/zsh
set -e

echo "👀 watching *.py for changes (poll) …"
TS=""
while true; do
  NEW=$(find . -maxdepth 1 -name "*.py" -exec stat -f "%m %N" {} \; 2>/dev/null | sort | md5)
  if [ "$NEW" != "$TS" ]; then
    TS="$NEW"
    ./refresh.sh
  fi
  sleep 1
done