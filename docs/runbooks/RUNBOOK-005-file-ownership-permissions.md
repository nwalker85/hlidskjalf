# RUNBOOK-005: File Ownership and Permissions

> **Purpose:** Standardize file ownership across all platform services using the ravenhelm user

---

## The Ravenhelm Platform User

All platform services run as a single standardized user:

```
┌─────────────────────────────────────────────────────────────┐
│                 RAVENHELM PLATFORM USER                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   User: ravenhelm                                           │
│   UID:  1001                                                │
│   GID:  1001                                                │
│                                                              │
│   Maps to Kubernetes: fsGroup: 1001                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Why a Single User?

| Before (Per-Service) | After (Ravenhelm) |
|---------------------|-------------------|
| PostgreSQL → 999:999 | All → 1001:1001 |
| Redis → 999:1000 | All → 1001:1001 |
| Grafana → 472:0 | All → 1001:1001 |
| Multiple SPIRE entries | One SPIRE entry |
| Complex init scripts | One init script |

### Benefits

1. **Simplicity**: One user to manage everywhere
2. **One SPIRE entry**: `unix:uid:1001` for all platform services
3. **K8s parity**: Maps directly to `fsGroup: 1001` in production
4. **Predictable**: New services just add `user: "1001:1001"`

---

## Platform Initialization

### First-Time Setup

Run the platform initialization script **once** before starting services:

```bash
./scripts/init-platform.sh
```

This script:
1. Creates all required Docker volumes
2. Sets ownership to ravenhelm (1001:1001)
3. Registers the SPIRE entry for `unix:uid:1001`

### What Gets Initialized

```
Certificate Volumes:
  hlidskjalf_postgres_certs  → 1001:1001
  hlidskjalf_redis_certs     → 1001:1001
  hlidskjalf_nats_certs      → 1001:1001

Data Volumes:
  hlidskjalf_postgres_data   → 1001:1001
  hlidskjalf_redis_data      → 1001:1001
  hlidskjalf_grafana_data    → 1001:1001
  ... etc
```

---

## Docker Compose Pattern

### Service Configuration

```yaml
# All services run as ravenhelm user
<service>:
  image: <image>
  user: "1001:1001"  # ravenhelm platform user
  volumes:
    - <service>_data:/data
    - <service>_certs:/run/spire/certs:ro
```

### Spiffe-Helper Sidecar

```yaml
<service>-spiffe-helper:
  image: spiffe-helper:local
  user: "1001:1001"  # ravenhelm - same as service!
  pid: "host"        # Required for SPIRE attestation
  volumes:
    - ./config/spiffe-helper/<service>-helper.conf:/etc/spiffe-helper/helper.conf:ro
    - <service>_certs:/run/spire/certs  # NO :ro - helper writes here
    - spire_agent_socket:/run/spire/sockets:ro
```

### SPIRE Entry

One entry for all platform services:

```bash
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry create \
    -parentID spiffe://ravenhelm.local/agent/local \
    -spiffeID spiffe://ravenhelm.local/workload/platform \
    -selector unix:uid:1001
```

---

## Adding a New Service

### 1. Add to docker-compose.yml

```yaml
my-new-service:
  image: my-image:latest
  user: "1001:1001"  # ravenhelm platform user
  labels:
    - "ravenhelm.project=hlidskjalf"
    - "ravenhelm.service=my-new-service"
    - "ravenhelm.workload=my-new-service"
  volumes:
    - my_new_service_data:/data
    - my_new_service_certs:/run/spire/certs:ro
  depends_on:
    my-new-service-spiffe-helper:
      condition: service_started

my-new-service-spiffe-helper:
  image: spiffe-helper:local
  user: "1001:1001"
  pid: "host"
  volumes:
    - ./config/spiffe-helper/my-new-service-helper.conf:/etc/spiffe-helper/helper.conf:ro
    - my_new_service_certs:/run/spire/certs
    - spire_agent_socket:/run/spire/sockets:ro
```

### 2. Add to init-platform.sh

```bash
# In CERT_VOLUMES array
CERT_VOLUMES=(
    ...
    "my_new_service_certs"
)

# In DATA_VOLUMES array  
DATA_VOLUMES=(
    ...
    "my_new_service_data"
)
```

### 3. Run initialization

```bash
./scripts/init-platform.sh
```

That's it! No SPIRE entry needed - the service will be attested via `unix:uid:1001`.

---

## Verification

### Check Volume Ownership

```bash
docker run --rm -v hlidskjalf_postgres_certs:/certs alpine ls -la /certs/

# Expected output:
# drwxr-xr-x  2 1001 1001  svid.pem
# -rw-------  1 1001 1001  key.pem      ← Must be 1001:1001
# drwxr-xr-x  2 1001 1001  bundle.pem
```

### Check Service User

```bash
docker exec gitlab-sre-postgres id

# Expected output:
# uid=1001 gid=1001 groups=1001
```

### Check SPIRE Entry

```bash
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry show | grep "uid:1001"

# Should show entry with selector: unix:uid:1001
```

---

## Troubleshooting

### Service Can't Read Key

```
FATAL: could not load private key file "/run/spire/certs/key.pem": Permission denied
```

**Cause:** Volume not owned by 1001:1001  
**Fix:** Run `./scripts/init-platform.sh`

### SPIRE Attestation Fails

```
no identity issued
```

**Cause:** SPIRE entry not registered for uid 1001  
**Fix:** Run `./scripts/init-platform.sh` (registers SPIRE entry)

### Key Has Wrong Permissions

```
private key file "/path/key.pem" has group or world access
```

**Cause:** spiffe-helper config issue  
**Fix:** Ensure `key_file_mode = 0600` in helper config

---

## Kubernetes Migration

When moving to Kubernetes, the ravenhelm user maps directly to Pod Security Context:

```yaml
apiVersion: v1
kind: Pod
spec:
  securityContext:
    runAsUser: 1001
    runAsGroup: 1001
    fsGroup: 1001  # <-- All volumes owned by 1001
```

This provides seamless local-to-production parity.

---

## Related Runbooks

- RUNBOOK-004: SPIRE Management
- RUNBOOK-006: Adding New Services with mTLS
