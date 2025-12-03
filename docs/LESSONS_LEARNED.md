# Lessons Learned - Enterprise Scaffolding

This document captures key architectural decisions, troubleshooting insights, and best practices discovered while building the Hliðskjálf platform.

---

## 1. File Ownership and Permissions: The `ravenhelm` User Pattern

### Problem
Inconsistent file ownership across Docker containers caused permission denied errors, particularly with SPIRE-generated certificates. Different containers ran as different users (`root`, `app`, `postgres`, etc.), leading to conflicts when sharing mounted volumes.

### Solution
Standardize on a single non-root user across all platform services:

```yaml
# Standard user: ravenhelm
# UID: 1001
# GID: 1001
```

**Key Decisions:**
- All platform services run as `ravenhelm:ravenhelm` (1001:1001)
- Kubernetes-compatible: UID 1001 aligns with typical `fsGroup` settings
- Volume initialization script (`scripts/init-platform.sh`) creates directories with correct ownership
- SPIRE entries registered for `unix:uid:1001` workload attestation

**References:**
- `docs/runbooks/RUNBOOK-005-file-ownership-permissions.md`

---

## 2. Observability Stack: Grafana Alloy over Separate Collectors

### Problem
Originally deployed separate collectors:
- Promtail for logs
- OTEL Collector for traces
- Prometheus for metrics

This created configuration drift, version incompatibilities, and increased operational complexity.

### Solution
**Grafana Alloy** - A unified collection agent that replaces all three:

| Old Stack | Alloy Equivalent |
|-----------|------------------|
| Promtail | `loki.source.docker` / `loki.source.file` |
| OTEL Collector | `otelcol.receiver.otlp` + exporters |
| Grafana Agent | Built into Alloy |
| Prometheus scraping | `prometheus.scrape` |

**Benefits:**
- Single configuration file (`config.alloy`)
- Native OTEL SDK support (applications can use `opentelemetry-sdk`)
- Hot-reload configuration without restarts
- Built-in service discovery for Docker
- Unified troubleshooting through Alloy UI

**Trade-off:** New River configuration language has a learning curve.

---

## 3. Docker Log Collection on macOS: Use `loki.source.docker`

### Problem
Standard log collection methods failed on macOS Docker Desktop:

```alloy
# FAILED: File paths don't exist on macOS
loki.source.file "docker_logs" {
  targets = [{ __path__ = "/var/lib/docker/containers/**/*.log" }]
}
```

Docker Desktop on macOS runs containers in a VM, so `/var/lib/docker/containers` is not accessible from the host filesystem.

### Solution
Use `loki.source.docker` which connects directly to the Docker socket:

```alloy
loki.source.docker "docker_logs" {
  host       = "unix:///var/run/docker.sock"
  targets    = discovery.docker.containers.targets
  forward_to = [loki.process.docker_logs.receiver]
}

discovery.docker "containers" {
  host = "unix:///var/run/docker.sock"
  filter {
    name   = "status"
    values = ["running"]
  }
}
```

**Key Insight:** Mount `/var/run/docker.sock` into the Alloy container.

---

## 4. Docker Log Parsing: Use `stage.docker {}` for Robustness

### Problem
Complex regex-based log parsing pipelines broke on non-JSON logs:

```alloy
# FRAGILE: Assumes JSON logs
stage.json {
  expressions = { message = "msg", level = "level" }
}
```

Not all containers output JSON logs. Some use logfmt, plain text, or inconsistent formats.

### Solution
Use the built-in Docker stage which handles multiple formats:

```alloy
loki.process "docker_logs" {
  forward_to = [loki.write.loki.receiver]
  
  // Handles JSON, logfmt, and plain text automatically
  stage.docker {}
  
  // Optionally extract level from common patterns
  stage.regex {
    expression = "(?i)(level=|\\s)(debug|info|warn|warning|error|fatal|panic|critical)\\b"
  }
}
```

**Key Insight:** `stage.docker {}` is designed to parse Docker's log JSON wrapper while preserving the inner message regardless of format.

---

## 5. Alloy State Management: Reset Volume After Container Changes

### Problem
After restarting containers, Alloy would lose track of log positions and show errors:

```
error inspecting Docker container: No such container
could not transfer logs
```

### Solution
When containers are recreated (not just restarted), Alloy's position database can become stale. Full reset procedure:

```bash
# Stop Alloy
docker compose stop alloy

# Remove the data volume
docker volume rm hlidskjalf_alloy_data

# Restart Alloy (will recreate volume)
docker compose up -d alloy
```

**Key Insight:** Alloy tracks log positions by container ID. When a container is recreated, it gets a new ID, but Alloy may still reference the old one.

---

## 6. Traefik as Unified Ingress over Multiple Nginx Proxies

### Problem
Multiple nginx proxy containers (one per service subdomain) created:
- Configuration sprawl
- Inconsistent TLS handling
- Port conflicts
- Difficult debugging

### Solution
Single Traefik instance as the unified edge proxy:

```yaml
# All traffic through one ingress
traefik:
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./dynamic.yml:/etc/traefik/dynamic.yml
```

**Benefits:**
- One place for all routing rules
- Automatic TLS termination
- Dashboard for debugging (`traefik.ravenhelm.test`)
- Docker labels for service discovery (optional)

**References:**
- `docs/architecture/TRAEFIK_MIGRATION_PLAN.md`
- `docs/runbooks/RUNBOOK-002-add-traefik-domain.md`

---

## 7. Zitadel SSO: Internal vs External URLs

### Problem
Grafana and other services failed to exchange tokens with Zitadel:

```
dial tcp 127.0.0.1:443: connect: connection refused
```

Services inside Docker tried to reach `zitadel.ravenhelm.test` which resolved to localhost inside the container.

### Solution
Use internal Docker URLs for server-to-server communication:

```yaml
# For browser redirects (external)
GF_AUTH_GENERIC_OAUTH_AUTH_URL: https://zitadel.ravenhelm.test/oauth/v2/authorize

# For backend token exchange (internal)
GF_AUTH_GENERIC_OAUTH_TOKEN_URL: http://zitadel:8080/oauth/v2/token
```

Alternative: Use `extra_hosts` to resolve external domain to Docker host:

```yaml
extra_hosts:
  - "zitadel.ravenhelm.test:host-gateway"
```

---

## 8. Zitadel Version: v2.62.1 for Built-in Login UI

### Problem
Zitadel v4.x returns 404 for `/ui/v2/login`:

```
GET /ui/v2/login/login?authRequest=... → 404
```

Zitadel v4 separates the login UI into a separate deployment.

### Solution
Pin to v2.62.1 which includes the built-in login UI:

```yaml
zitadel:
  image: ghcr.io/zitadel/zitadel:v2.62.1
```

**Key Insight:** For local development, the built-in UI is simpler. Production may use the new hosted login v2.

---

## 9. Port Conflict Debugging with `lsof`

### Problem
Container startup failed with "port already allocated":

```
Bind for 0.0.0.0:4317 failed: port is already allocated
```

### Solution
Use `lsof` to identify the conflicting process:

```bash
lsof -i :4317
# Shows which process holds the port

# If it's an old container
docker ps -a | grep 4317
docker stop <container_id>
```

---

## 10. Dashboard Provisioning: Grafana Auto-Discovery

### Problem
Manually creating dashboards through the UI is tedious and not version-controlled.

### Solution
Use Grafana's provisioning system:

```
observability/grafana/provisioning/
├── dashboards/
│   ├── default.yml              # Dashboard provider config
│   └── json/
│       ├── platform-overview.json
│       ├── service-health.json
│       └── infrastructure.json
└── datasources/
    └── datasources.yml
```

**Key Insight:** Dashboards placed in `json/` are auto-loaded on Grafana startup. Changes require `docker compose restart grafana`.

---

## 11. Grafana Datasource UIDs: Always Specify Explicitly

### Problem
Dashboards showed "Prometheus not found" even though Prometheus was running and healthy. Manually running queries in panels worked, but dashboards failed to load data.

```json
// Dashboard JSON references datasource by UID
"datasource": {
  "type": "prometheus",
  "uid": "prometheus"  // ← Expected UID
}
```

### Root Cause
The `datasources.yml` didn't specify explicit UIDs:

```yaml
# BAD: No UID specified → Grafana auto-generates random UID
- name: Prometheus
  type: prometheus
  url: http://prometheus:9090
```

Grafana auto-generates UIDs like `dXJuOmdyYWZhbmE6...` when not specified, which don't match the `"uid": "prometheus"` in the dashboard JSON.

### Solution
Always specify explicit UIDs in `datasources.yml`:

```yaml
# GOOD: Explicit UID matches dashboard references
- name: Prometheus
  type: prometheus
  url: http://prometheus:9090
  uid: prometheus  # ← Must match dashboard JSON

- name: Loki
  type: loki
  url: http://loki:3100
  uid: loki

- name: Tempo
  type: tempo
  url: http://tempo:3200
  uid: tempo
```

### Migration Steps
If datasources already exist with auto-generated UIDs:

```bash
# 1. Stop Grafana
docker compose stop grafana

# 2. Remove the data volume (clears stale datasource records)
docker volume rm hlidskjalf_grafana_data

# 3. Update datasources.yml with explicit UIDs

# 4. Start Grafana fresh
docker compose up -d grafana
```

**Key Insight:** Grafana's provisioning won't update UIDs on existing datasources - you need a clean slate.

---

## 12. GitLab SSO with Zitadel: Certificate Trust Chain

### Problem
GitLab OIDC authentication failed with SSL certificate verification error:

```
Ssl connect returned=1 errno=0 peeraddr=192.168.65.254:443 state=error: certificate verify failed (unable to get local issuer certificate)
```

GitLab couldn't verify Zitadel's certificate because it was signed by a local CA (mkcert) that GitLab didn't trust.

### Solution
Mount the mkcert CA certificate into GitLab's trusted certificates directory:

```yaml
gitlab:
  entrypoint:
    - /bin/sh
    - -c
    - |
      mkdir -p /etc/gitlab/trusted-certs &&
      cp /certs/mkcert-ca.crt /etc/gitlab/trusted-certs/mkcert-ca.crt 2>/dev/null || true &&
      exec /assets/init-container
  volumes:
    - ./ravenhelm-proxy/config/certs/mkcert-ca.crt:/certs/mkcert-ca.crt:ro
```

**Key Insight:** GitLab processes certificates in `/etc/gitlab/trusted-certs/` during reconfigure, creating symlinks and adding them to the system trust store. The entrypoint script copies the CA before reconfigure runs.

**Important:** Verify which CA signed your server certificates:
```bash
openssl s_client -connect zitadel.ravenhelm.test:443 -servername zitadel.ravenhelm.test 2>/dev/null | grep issuer
```

---

## 13. GitLab Organizations: Required for Groups (GitLab 17+)

### Problem
Creating a GitLab group failed with:
```
Validation failed: Organization can't be blank
```

### Solution
GitLab 17+ requires groups to belong to an Organization:

```ruby
# Create organization first
org = Organizations::Organization.create!(
  name: "Ravenhelm",
  path: "ravenhelm",
  visibility_level: 0  # Private
)

# Then create group under the organization
group = Group.new(
  name: "Ravenhelm",
  path: "ravenhelm",
  organization: org  # Required!
)
group.save!
```

**Key Insight:** Organizations are a new concept in GitLab CE 17+ (previously EE-only). Always specify the organization when creating groups programmatically.

---

## 14. GitLab Admin Assignment: Not Automatic via OIDC

### Problem
GitLab CE doesn't support automatic admin assignment based on OIDC claims/roles.

### Solution
After a user logs in via SSO, promote them to admin via Rails console:

```bash
docker exec gitlab-sre-gitlab gitlab-rails runner '
user = User.find_by(username: "USERNAME")
user.admin = true
user.save!
'
```

For automation, use the GitLab API with an admin token (see RUNBOOK-009).

**Future:** Implement a webhook handler that:
1. Receives GitLab `user_create` events
2. Queries Zitadel for the user's roles
3. Updates GitLab permissions via API

---

## Summary Checklist

When setting up a new platform instance:

- [ ] Initialize volumes with `ravenhelm` user (UID 1001)
- [ ] Deploy Grafana Alloy (not separate collectors)
- [ ] Mount Docker socket for log collection
- [ ] Use `stage.docker {}` for log parsing
- [ ] Single Traefik instance for ingress
- [ ] Separate internal/external URLs for SSO
- [ ] Pin Zitadel to v2.62.1 for built-in login
- [ ] Provision dashboards via filesystem, not UI
- [ ] Specify explicit UIDs in Grafana datasources.yml
- [ ] Mount mkcert CA into GitLab for Zitadel OIDC
- [ ] Create Organization before Groups in GitLab 17+
- [ ] Promote first admin user via Rails console after SSO login

