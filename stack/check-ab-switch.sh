#!/bin/sh
set -eu

base_url="${LINK_HOARDER_AB_URL:-http://127.0.0.1:8080}"
temp_dir=$(mktemp -d)
trap 'rm -rf "$temp_dir"' EXIT HUP INT TERM

check_variant() {
    variant=$1
    headers="$temp_dir/$variant.headers"
    cookies="$temp_dir/$variant.cookies"
    html="$temp_dir/$variant.html"

    curl --silent --show-error \
        --dump-header "$headers" \
        --cookie-jar "$cookies" \
        --output /dev/null \
        "$base_url/?version=$variant"

    grep -Eq '^HTTP/[0-9.]+ 303 ' "$headers"
    tr -d '\r' < "$headers" | grep -qx 'Location: /'
    awk -v expected="$variant" '
        !/^#/ && $6 == "link_hoarder_variant" && $7 == expected { found = 1 }
        END { exit found ? 0 : 1 }
    ' "$cookies"

    curl --fail --silent --show-error --location \
        --cookie "$cookies" \
        --cookie-jar "$cookies" \
        "$base_url/?version=$variant" \
        --output "$html"

    for asset in $(grep -oE '/assets/[^" ]+\.(js|css)' "$html"); do
        body="$temp_dir/$(basename "$asset")"
        curl --fail --silent --show-error \
            --cookie "$cookies" \
            "$base_url$asset" \
            --output "$body"
        if grep -qi '<!doctype html>' "$body"; then
            echo "$variant asset returned the frontend fallback: $asset" >&2
            exit 1
        fi
    done
}

check_variant stable
check_variant staging

if cmp --silent "$temp_dir/stable.html" "$temp_dir/staging.html"; then
    echo "Stable and Staging returned the same HTML." >&2
    exit 1
fi

printf 'A/B switching is healthy at %s.\n' "$base_url"
