#!/bin/sh
# Seed the Docker web stack from the host CLI database via bulk JSON import.
# Skips cleanly when no CLI database exists. Idempotent: reruns report
# duplicates as skipped.
set -eu

port="${LINK_HOARDER_PORT:-8080}"
db="${LINK_HOARDER_DATABASE_PATH:-$HOME/.local/share/link-hoarder/bookmarks.db}"

if [ ! -s "$db" ]; then
  echo "No CLI database at $db; nothing to seed."
  exit 0
fi

base="http://127.0.0.1:$port"
attempt=0
until curl --fail --silent --output /dev/null "$base/health"; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "Web stack is not healthy at $base/health." >&2
    exit 1
  fi
  sleep 1
done

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
uv run link-hoarder export --no-interactive "$tmp" >/dev/null
curl --fail --show-error \
  --header "Content-Type: application/json" \
  --data-binary "@$tmp/json/bookmarks.json" \
  "$base/api/v1/imports/bookmarks-json"
echo ""
