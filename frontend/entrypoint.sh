#!/bin/sh
set -eu

key_file=/run/link-hoarder/api-key
until [ -s "$key_file" ]; do
    sleep 0.1
done

LINK_HOARDER_API_KEY=$(cat "$key_file")
export LINK_HOARDER_API_KEY
export API_UPSTREAM="${API_UPSTREAM:-api:8000}"

exec /docker-entrypoint.sh "$@"
