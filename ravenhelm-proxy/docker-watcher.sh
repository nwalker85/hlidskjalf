#!/bin/bash

# Docker Desktop Watcher
# Monitors Docker Desktop and restarts it if not running

POLL_INTERVAL=${POLL_INTERVAL:-10}  # Check every 10 seconds by default
MAX_WAIT=${MAX_WAIT:-60}            # Max seconds to wait for Docker to start
DOCKER_APP="/Applications/Docker.app"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

is_docker_running() {
    # Check if Docker daemon is responsive
    docker info >/dev/null 2>&1
    return $?
}

is_docker_app_running() {
    # Check if Docker Desktop app process is running
    pgrep -x "Docker Desktop" >/dev/null 2>&1
    return $?
}

start_docker() {
    log "Starting Docker Desktop..."
    open -a "$DOCKER_APP"

    # Wait for Docker to become responsive
    local waited=0
    while [ $waited -lt $MAX_WAIT ]; do
        if is_docker_running; then
            log "Docker Desktop is now running and responsive"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
        log "Waiting for Docker to start... (${waited}s/${MAX_WAIT}s)"
    done

    log "WARNING: Docker started but not responsive after ${MAX_WAIT}s"
    return 1
}

main() {
    log "Docker Desktop Watcher started"
    log "Poll interval: ${POLL_INTERVAL}s, Max wait: ${MAX_WAIT}s"

    # Check if Docker.app exists
    if [ ! -d "$DOCKER_APP" ]; then
        log "ERROR: Docker Desktop not found at $DOCKER_APP"
        exit 1
    fi

    while true; do
        if ! is_docker_running; then
            if is_docker_app_running; then
                log "Docker Desktop app is running but daemon is not responsive"
            else
                log "Docker Desktop is not running"
            fi
            start_docker
        fi
        sleep "$POLL_INTERVAL"
    done
}

# Handle graceful shutdown
trap 'log "Watcher stopped"; exit 0' SIGINT SIGTERM

main
