# RUNBOOK-029: Service-as-an-Agent (SAAA) Integration

## 1. Overview

`serviceasanagent` is the Quant reference implementation of the “Service-as-an-Agent” architecture (voice-first LangGraph mesh). This runbook documents how to align the repo at `/Users/nwalker/Development/Quant/Projects/serviceasanagent` with the shared Ravenhelm platform (Traefik, port registry, `platform_net`, Traefik routing, and documentation).

| Component | Purpose | External Host | Internal Port |
|-----------|---------|---------------|---------------|
| `frontend` | Next.js operator console | `saaa.ravenhelm.test` / `frontend.saaa.ravenhelm.test` | 3000 |
| `voice-io-agent` (via nginx) | Voice/LLM API | `api.saaa.ravenhelm.test` | 8000 |
| `deep-agent`/`research-agent`/`analysis-agent` (via nginx) | Direct LangGraph access | `agents.saaa.ravenhelm.test` | 8000 |
| `redpanda-console` (via nginx) | Kafka monitoring | `kafka.saaa.ravenhelm.test` | 8080 |
| Infrastructure/Core/Capability agent routers | Access control to Tier 1–3 agents | `infra.*`, `core.*`, `capability.*` | 8000 |

Nginx remains the internal router, but TLS is now terminated at Traefik. All HTTP traffic flows over `platform_net`.

---

## 2. Port Registry Entry

`config/port_registry.yaml` now includes:

```yaml
work:
  serviceasanagent:
    path: ~/Development/Quant/Projects/serviceasanagent
    api_port: 8209
    ui_port: 3208
    domain: saaa.ravenhelm.test
    domain_aliases:
      - frontend.saaa.ravenhelm.test
      - api.saaa.ravenhelm.test
      - agents.saaa.ravenhelm.test
      - kafka.saaa.ravenhelm.test
      - infra.saaa.ravenhelm.test
      - core.saaa.ravenhelm.test
      - capability.saaa.ravenhelm.test
```

Use these hostnames when generating certificates or wiring new clients.

---

## 3. Environment Configuration

Create/merge the following overrides in `/Users/nwalker/Development/Quant/Projects/serviceasanagent/.env` so the frontend and agents target the new domains:

```bash
NEXT_PUBLIC_API_URL=https://api.saaa.ravenhelm.test
NEXT_PUBLIC_AGENTS_URL=https://agents.saaa.ravenhelm.test
NEXT_PUBLIC_KAFKA_CONSOLE_URL=https://kafka.saaa.ravenhelm.test
```

If you need to test locally without Traefik, override these back to `localhost` before running `docker compose up`.

---

## 4. Networking Alignment

1. Ensure the shared network exists:  
   `/Users/nwalker/Development/hlidskjalf/scripts/create_traefik_networks.sh`.
2. `docker-compose.yml` adds `platform_net` as an external network and attaches the `nginx` ingress container to it (in addition to the internal `saaa-network` / `saaa-integration` tiers). No other service needs to join `platform_net`.
3. Nginx now listens on plaintext `8080` and trusts the new `*.ravenhelm.test` hostnames. Traefik terminates TLS and forwards HTTP to `saaa-nginx` over `platform_net`.

---

## 5. Docker Compose Updates

Key changes committed to the repo:

- `nginx` service
  - `container_name: saaa-nginx`
  - Removed host `80/443` bindings
  - Added `platform_net` to its `networks` section
- `frontend` service
  - Added env fallbacks for the new domains (`NEXT_PUBLIC_*` variables)
- Global `networks`
  - Declared `platform_net` as `external: true`

Run `docker compose up -d nginx frontend voice-io-agent ...` after pulling to ensure the new network attachment takes effect.

---

## 6. Traefik Integration

`ravenhelm-proxy/dynamic.yml` now contains routers + a shared service for SAAA:

| Router | Host Rule | Middleware | Backend |
|--------|-----------|------------|---------|
| `saaa-frontend` | `saaa.ravenhelm.test`, `frontend.saaa.ravenhelm.test` | `secure-headers` | `saaa-nginx-svc` |
| `saaa-api` | `api.saaa.ravenhelm.test` | `cors-all`, `secure-headers` | `saaa-nginx-svc` |
| `saaa-agents` | `agents.saaa.ravenhelm.test` | `protected` | `saaa-nginx-svc` |
| `saaa-kafka` | `kafka.saaa.ravenhelm.test` | `protected` | `saaa-nginx-svc` |
| `saaa-infra` / `saaa-core` / `saaa-capability` | respective hosts | `protected` | `saaa-nginx-svc` |

The shared service points to `http://saaa-nginx:8080`.

Reload Traefik:

```bash
cd /Users/nwalker/Development/hlidskjalf/ravenhelm-proxy
docker compose -f docker-compose-traefik.yml up -d traefik
```

---

## 7. Validation Checklist

- [ ] `docker compose ps` (inside `serviceasanagent`) shows all containers healthy (no port collisions with Traefik).
- [ ] `curl -sk https://saaa.ravenhelm.test` returns the Next.js HTML shell.
- [ ] `curl -sk https://api.saaa.ravenhelm.test/health` returns the voice-io agent health payload.
- [ ] `curl -sk https://agents.saaa.ravenhelm.test/deep/health` (and `research/`, `analysis/`) succeed.
- [ ] `curl -sk https://kafka.saaa.ravenhelm.test` responds (may require `-k` if backend enforces auth).
- [ ] Frontend loads via Traefik and can reach the API (check browser network tab).

---

## References

- `/Users/nwalker/Development/Quant/Projects/serviceasanagent/docker-compose.yml`
- `/Users/nwalker/Development/Quant/Projects/serviceasanagent/config/nginx/nginx.conf`
- `/Users/nwalker/Development/hlidskjalf/ravenhelm-proxy/dynamic.yml`
- `/Users/nwalker/Development/hlidskjalf/config/port_registry.yaml`

