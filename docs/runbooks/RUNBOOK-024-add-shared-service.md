# RUNBOOK-024: Add a New Shared Service

This runbook explains how to introduce a new platform-level service (e.g., LiveKit, MCP backends) so it is consistently registered in the port registry, added to Docker Compose, protected by SPIRE/TLS, and exposed via Traefik.

---

## 1. Gather Prerequisites

1. **Service metadata**: name, purpose, maintainers.
2. **Port requirements**: internal container ports, external ports (if applicable), and whether the service needs HTTPS/mTLS.
3. **Security posture**: does it need SPIFFE SVIDs, OAuth forward auth, secrets from LocalStack, etc.?

### Shared network layout

- **`platform_net`** – the shared platform network (actual Docker network `platform_net`). All foundational services (Postgres, Zitadel, Redis, NATS, LocalStack) and management/control-plane workloads (GitLab, LangGraph/Norns, Bifrost, Traefik) must attach here so they can communicate without ad‑hoc links. Traefik listens on this network, so any service that needs an HTTP route should join `platform_net`.
- **`edge`** – Traefik’s public-facing entry network for ports 80/443. Only the edge proxy needs to attach.
- **Per-project nets** (e.g., `saaa_net`, `m2c_net`, `tinycrm_net`) – optional isolated networks for customer/demo stacks. Traefik can also join these when those stacks need routing, but shared services stay on `platform_net`.

When adding a new shared service, join `platform_net` by default; add extra networks only if the service must live inside an isolated stack.

---

## 2. Reserve Ports in `config/port_registry.yaml`

1. Open `[config/port_registry.yaml](config/port_registry.yaml)`.
2. Add an entry with:
   - `service`: descriptive name (e.g., `livekit`).
   - `port`: external port (or range).
   - `internal_port`: container port.
   - `category`: e.g., `realtime`, `observability`, `ai`.
   - `status` / `notes`.
3. If the service will be fronted by Traefik only, still document the internal port to avoid conflicts.

Example snippet:
```yaml
- service: livekit
  category: realtime
  port: 7880
  internal_port: 7880
  status: planned
  notes: LiveKit HTTP / WebSocket API
```

Commit this change before modifying compose files to keep port assignments auditable.

---

## 3. Define the Service in `docker-compose.yml`

1. Choose an insertion point in `[docker-compose.yml](docker-compose.yml)` near related services.
2. Add the container block:
   - `build` or `image`.
   - `container_name` = `gitlab-sre-<service>`.
   - Labels (`ravenhelm.project`, `ravenhelm.service`, `ravenhelm.workload`).
   - `environment` (secrets from LocalStack, SSO endpoints, etc.).
   - `ports` only if the service must be reachable directly (most routed services omit host ports).
   - `volumes` for configs/certs/data.
   - `depends_on` (SPIRE helper, databases, etc.).
   - `networks`: usually `platform_net`.
3. **SPIFFE/mTLS** (if needed):
   - Add a named volume (`<service>_certs`) and mount at `/run/spire/certs:ro`.
   - Define a sidecar `spiffe-helper` entry (mirroring postgres/nats/redis or MCP examples) pointing to a helper config in `config/spiffe-helper/`.

Example helper config:
```toml
agent_address = "/run/spire/sockets/api.sock"
cert_dir = "/run/spire/certs"
svid_file_name = "svid.pem"
svid_key_file_name = "key.pem"
svid_bundle_file_name = "bundle.pem"
add_intermediates_to_bundle = true
```

Update the `volumes:` section at the end of the compose file with any new named volumes.

---

## 4. Add Traefik Routing (`ravenhelm-proxy/dynamic.yml`)

1. **Router**: under `http.routers`, create a block:
   ```yaml
   my-service:
     rule: "Host(`service.ravenhelm.test`)"
     service: my-service-svc
     middlewares:
       - protected   # or zero-trust auth chain
     tls: {}
   ```
2. **Service**: under `http.services`, add:
   ```yaml
   my-service-svc:
     loadBalancer:
       serversTransport: my-service-transport   # optional, for mTLS
       servers:
         - url: "http://host.docker.internal:PORT"
   ```
   (If the backend listens on HTTPS/mTLS, include `serversTransport` referencing the TLS block.)
3. **Transport (optional)**: under `serversTransports`, define TLS settings (root CA, client cert/key) similar to `mcp-gitlab-transport`.
4. **Traefik restart**: `cd ravenhelm-proxy && docker compose -f docker-compose-traefik.yml restart traefik`.

---

## 5. Apply Zero-Trust Policies

1. For services without native SSO, add the `protected` middleware (Zitadel forward auth).
2. For services with their own OAuth, ensure they trust `oauth2-proxy`/Zitadel tokens by configuring client IDs/secrets.
3. Document the chosen approach in the service’s README or runbook.

---

## 6. Wiring Secrets (LocalStack)

1. Update `[localstack/init/init-aws.sh](localstack/init/init-aws.sh)` to create any needed secrets/parameters (API keys, client secrets).
2. Reference those secrets in `docker-compose.yml` via environment variables (`<SERVICE>_SECRET_NAME`).
3. If the service consumes secrets at runtime, ensure the code (or helper script) mirrors the approach in `services/mcp-server-gitlab/app/secrets.py`.

---

## 7. Testing & Validation

1. `docker compose build <service>` (if it’s a build context).
2. `docker compose up -d <service> [<service>-spiffe-helper]`.
3. Confirm logs: `docker compose logs -f <service>`.
4. Test via Traefik hostname (`curl -sk https://service.ravenhelm.test/healthz`).
5. Update Grafana dashboards (service inventory) if the new service should appear in observability panels.

---

## 8. Documentation & Tracking

1. Add/update runbooks or README sections describing the service purpose, configuration, and troubleshooting.
2. Update `docs/wikis/Architecture_Index.md` (or relevant wiki page) with a short description and link to the runbook.
3. If the service corresponds to a project plan item, move the GitLab issue to `workflow::done` once deployed.

---

## Quick Checklist

- [ ] Added entry to `config/port_registry.yaml`.
- [ ] Compose service + helper defined; named volumes updated.
- [ ] Traefik router/service/transport blocks added.
- [ ] Secrets created in LocalStack.
- [ ] Service starts cleanly (`docker compose up -d …`).
- [ ] Endpoint reachable through Traefik.
- [ ] Documentation/runbooks updated.

