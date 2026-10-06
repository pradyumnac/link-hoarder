#!/bin/sh
set -eu

container=""
for file in stack/compose.ab.yaml stack/compose.yaml; do
    candidate=$(docker compose -f "$file" ps -q api 2>/dev/null || true)
    if [ -n "$candidate" ]; then
        container="$candidate"
        break
    fi
done
if [ -z "$container" ]; then
    echo "No running API container. Start the stack first." >&2
    exit 1
fi

docker exec "$container" python -c "
import sqlite3
connection = sqlite3.connect('/data/bookmarks.db')
rows = connection.execute(
    'select status, count(*) from bookmark_metadata group by status'
).fetchall()
covered = connection.execute(
    'select count(*) from bookmark_metadata where preview_title is not null'
).fetchone()[0]
total = sum(count for _, count in rows)
print(f'bookmarks with metadata rows: {total}')
for status, count in sorted(rows):
    print(f'  {status}: {count}')
print(f'rows with preview text: {covered}')
"
