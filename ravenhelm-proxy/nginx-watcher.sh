#!/bin/bash

# Nginx Container Watcher
# Monitors the ravenhelm-proxy nginx container and restarts it if not running

POLL_INTERVAL=${POLL_INTERVAL:-10}  # Check every 10 seconds by default
MAX_WAIT=${MAX_WAIT:-60}            # Max seconds to wait for container to start
COMPOSE_PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTAINER_NAME=${CONTAINER_NAME:-"ravenhelm-proxy-nginx-1"}

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

is_docker_running() {
    docker info >/dev/null 2>&1
    return $?
}

is_nginx_running() {
    # Check if nginx container is running and healthy
    local status
    status=$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null)
    [ "$status" = "true" ]
}

is_nginx_healthy() {
    # Check if nginx is actually responding
    docker exec "$CONTAINER_NAME" nginx -t >/dev/null 2>&1
    return $?
}

wait_for_docker() {
    local waited=0
    while [ $waited -lt $MAX_WAIT ]; do
        if is_docker_running; then
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
        log "Waiting for Docker... (${waited}s/${MAX_WAIT}s)"
    done
    return 1
}

start_nginx() {
    log "Starting nginx container..."
    cd "$COMPOSE_PROJECT_DIR" || exit 1

    docker compose up -d nginx

    # Wait for container to be running
    local waited=0
    while [ $waited -lt $MAX_WAIT ]; do
        if is_nginx_running && is_nginx_healthy; then
            log "Nginx container is now running and healthy"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
        log "Waiting for nginx to start... (${waited}s/${MAX_WAIT}s)"
    done

    log "WARNING: Nginx started but not healthy after ${MAX_WAIT}s"
    return 1
}

main() {
    log "Nginx Container Watcher started"
    log "Poll interval: ${POLL_INTERVAL}s, Max wait: ${MAX_WAIT}s"
    log "Compose project: $COMPOSE_PROJECT_DIR"
    log "Container name: $CONTAINER_NAME"

    while true; do
        # First ensure Docker is running
        if ! is_docker_running; then
            log "Docker is not running, waiting..."
            if ! wait_for_docker; then
                log "Docker not available after ${MAX_WAIT}s, will retry"
                sleep "$POLL_INTERVAL"
                continue
            fi
            log "Docker is now available"
            # Give Docker a moment to fully initialize
            sleep 5
        fi

        # Check nginx container
        if ! is_nginx_running; then
            log "Nginx container is not running"
            start_nginx
        elif ! is_nginx_healthy; then
            log "Nginx container is running but not healthy, restarting..."
            docker compose -f "$COMPOSE_PROJECT_DIR/docker-compose.yml" restart nginx
            sleep 5
        fi

        sleep "$POLL_INTERVAL"
    done
}

# Handle graceful shutdown
trap 'log "Watcher stopped"; exit 0' SIGINT SIGTERM

main
