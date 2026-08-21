#!/bin/sh
set -eu

key_file=/run/link-hoarder/api-key
mkdir -p "$(dirname "$key_file")"

if [ -n "${LINK_HOARDER_API_KEY:-}" ]; then
    printf '%s' "$LINK_HOARDER_API_KEY" > "$key_file"
elif [ ! -s "$key_file" ]; then
    python -c 'import secrets; print(secrets.token_urlsafe(48), end="")' > "$key_file"
fi

chmod 600 "$key_file"
LINK_HOARDER_API_KEY=$(cat "$key_file")
export LINK_HOARDER_API_KEY

exec "$@"
