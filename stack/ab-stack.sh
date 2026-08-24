#!/bin/sh
set -eu

normal_compose="stack/compose.yaml"
ab_compose="stack/compose.ab.yaml"
stable_image="link-hoarder-frontend:stable"
staging_image="link-hoarder-frontend:staging"

ab_enabled() {
    value="${LINK_HOARDER_AB_ENABLED:-}"
    if [ -z "$value" ] && [ -f stack/.env ]; then
        value=$(awk -F= '/^[[:space:]]*LINK_HOARDER_AB_ENABLED[[:space:]]*=/{value=$2} END{gsub(/[[:space:]"]/, "", value); print value}' stack/.env)
    fi
    [ "$value" = "true" ]
}

require_ab() {
    if ! ab_enabled; then
        echo "Set LINK_HOARDER_AB_ENABLED=true in stack/.env before you use an A/B task." >&2
        exit 2
    fi
}

build_stable() {
    docker build \
        --build-arg VITE_AB_SWITCHING_ENABLED=true \
        --file frontend/Dockerfile \
        --tag "$stable_image" .
}

ensure_stable() {
    if ! docker image inspect "$stable_image" >/dev/null 2>&1; then
        echo "Build the initial stable frontend image."
        build_stable
    fi
}

ensure_staging() {
    if ! docker image inspect "$staging_image" >/dev/null 2>&1; then
        docker tag "$stable_image" "$staging_image"
    fi
}

restart_proxy() {
    docker compose --file "$ab_compose" restart proxy
}

command="${1:-}"
case "$command" in
    up)
        if ab_enabled; then
            ensure_stable
            ensure_staging
            docker compose --file "$ab_compose" up --build --detach --remove-orphans
        else
            docker compose --file "$normal_compose" up --build --detach --remove-orphans
        fi
        ;;
    serve)
        if ab_enabled; then
            ensure_stable
            ensure_staging
            docker compose --file "$ab_compose" up --build --remove-orphans
        else
            docker compose --file "$normal_compose" up --build --remove-orphans
        fi
        ;;
    deploy-staging)
        require_ab
        ensure_stable
        docker compose --file "$ab_compose" build frontend-staging
        docker compose --file "$ab_compose" up --detach frontend-staging proxy
        restart_proxy
        ;;
    promote)
        require_ab
        build_stable
        docker compose --file "$ab_compose" up --detach --no-deps frontend-stable
        restart_proxy
        ;;
    reset-staging)
        require_ab
        ensure_stable
        docker tag "$stable_image" "$staging_image"
        docker compose --file "$ab_compose" up --detach --no-deps --force-recreate frontend-staging
        restart_proxy
        ;;
    down)
        docker compose --file "$normal_compose" down --remove-orphans
        docker compose --file "$ab_compose" down --remove-orphans
        ;;
    *)
        echo "Usage: $0 {up|serve|deploy-staging|promote|reset-staging|down}" >&2
        exit 2
        ;;
esac
