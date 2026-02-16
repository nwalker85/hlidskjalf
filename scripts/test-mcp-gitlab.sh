#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🚦 Checking MCP GitLab server authentication..."
docker compose exec -T mcp-server-gitlab python - <<'PY'
import json
import sys

import httpx

try:
    resp = httpx.get(
        "https://localhost:9400/healthz/gitlab",
        timeout=5.0,
        verify=False,
        cert=(
            "/run/spire/certs/svid.pem",
            "/run/spire/certs/key.pem",
        ),
    )
    resp.raise_for_status()
except Exception as exc:  # noqa: BLE001
    print(f"GitLab health check failed: {exc}", file=sys.stderr)
    sys.exit(1)

data = resp.json()
print(json.dumps(data, indent=2))
PY
echo "✅ MCP GitLab auth check passed."

