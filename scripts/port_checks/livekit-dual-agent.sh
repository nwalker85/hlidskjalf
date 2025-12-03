#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
python3 "$REPO_ROOT/scripts/check_ports.py" --project livekit-dual-agent "$@"
