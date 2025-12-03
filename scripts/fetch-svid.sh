#!/bin/bash
# =============================================================================
# SVID Fetcher Script
# Fetches X.509 SVID from SPIRE agent and writes to specified directory
# =============================================================================

set -e

SOCKET_PATH="${SPIRE_AGENT_SOCKET:-/run/spire/sockets/api.sock}"
OUTPUT_DIR="${CERT_OUTPUT_DIR:-/run/spire/certs}"
REFRESH_INTERVAL="${SVID_REFRESH_INTERVAL:-3600}"

mkdir -p "$OUTPUT_DIR"

fetch_svid() {
    echo "[$(date)] Fetching SVID from SPIRE agent..."
    
    # Use spire-agent to fetch SVID
    # This requires the agent socket to be mounted
    if [ -S "$SOCKET_PATH" ]; then
        # Using go-spiffe or spire-agent api fetch
        # For now, just create placeholder files
        echo "[$(date)] Socket found at $SOCKET_PATH"
        echo "[$(date)] SVID fetch would happen here"
    else
        echo "[$(date)] WARNING: SPIRE agent socket not found at $SOCKET_PATH"
        echo "[$(date)] Waiting for SPIRE agent..."
        sleep 5
    fi
}

# Initial fetch
fetch_svid

# If running as daemon, keep refreshing
if [ "${DAEMON_MODE:-false}" = "true" ]; then
    while true; do
        sleep "$REFRESH_INTERVAL"
        fetch_svid
    done
fi

