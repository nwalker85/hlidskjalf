# RUNBOOK-023: MCP GitLab Server

## Purpose

Expose GitLab administration and knowledge-base utilities to the Norns agents via the Model Context Protocol (MCP). This runbook covers deployment, configuration, and day-two operations of the `mcp-server-gitlab` service that now ships in `docker-compose.yml`.

---

## 1. Architecture Snapshot

```
┌───────────────┐        MCP HTTP/JSON-RPC        ┌──────────────────────────────┐
│   Bifrost /   │ ───────────────────────────────▶ │  mcp-server-gitlab (FastAPI) │
│   Norns MCP   │                                 │   • GitLab SDK               │
│   Backend     │ ◀─────────────────────────────── │   • Knowledge tools          │
└───────────────┘        Tool responses           └──────────────┬──────────────┘
                                                                │ REST / GraphQL
                                                         ┌───────┴────────┐
                                                         │ GitLab CE      │
                                                         └────────────────┘
```

- Access is routed through Traefik at `https://mcp.gitlab.ravenhelm.test`, inheriting the zero-trust forward-auth middleware (Zitadel SSO + oauth2-proxy).
- Service listens on port `9400` inside Docker (`services/mcp-server-gitlab`).
- Secrets (GitLab PAT, wiki token) are fetched from LocalStack Secrets Manager (`ravenhelm/dev/gitlab/mcp_service`).

---

## 2. Prerequisites

1. **Valid GitLab tokens**
   - PAT with `api` scope stored in LocalStack: `ravenhelm/dev/gitlab/mcp_service`.
     ```bash
     awslocal secretsmanager put-secret-value \
       --secret-id ravenhelm/dev/gitlab/mcp_service \
       --secret-string '{"token":"<GITLAB_PAT>","wiki_token":"<WIKI_TOKEN>"}'
     ```
   - `wiki_token` can match the PAT until a dedicated token is created.
2. **Zitadel service account credentials**
   - Stored in LocalStack Secrets Manager: `ravenhelm/dev/zitadel/service_account`.
   - The JSON payload must include `id` and `token`. Override at runtime with `ZITADEL_SERVICE_ACCOUNT_TOKEN` only for testing.
3. **DNS & Certificates**
   - `mcp.gitlab.ravenhelm.test` must resolve to Traefik (already set via dnsmasq/mkcert).
4. **GitLab project location**
   - Repository + wiki live at `https://gitlab.ravenhelm.test/ravenhelm/hlidskjalf`. Ensure repo is reachable inside Docker (`http://gitlab` on the internal network).

---

## 3. Configuration Reference

Service definition (excerpt from `docker-compose.yml`):

```yaml
  mcp-server-gitlab:
    build:
      context: ./services/mcp-server-gitlab
    environment:
      - GITLAB_BASE_URL=https://gitlab.ravenhelm.test
      - GITLAB_API_URL=http://gitlab          # internal URL for lower latency
      - GITLAB_PROJECT_PATH=ravenhelm/hlidskjalf
      - GITLAB_VERIFY_SSL=false               # local dev certs
      - GITLAB_MCP_SECRET_NAME=ravenhelm/dev/gitlab/mcp_service
      - LOCALSTACK_ENDPOINT=http://localstack:4566
      - AWS_ACCESS_KEY_ID=test
      - AWS_SECRET_ACCESS_KEY=test
      - AWS_REGION=us-east-1
      - MCP_SERVICE_PORT=9400
```

Important knobs:

| Variable | Description |
|----------|-------------|
| `GITLAB_BASE_URL` | External HTTPS URL (used for returned links). |
| `GITLAB_API_URL` | Internal URL for the GitLab CE instance. |
| `GITLAB_PROJECT_PATH` | Default repo/wikis to act against. |
| `GITLAB_MCP_SECRET_NAME` | Secrets Manager entry containing PAT & wiki token. |
| `KNOWLEDGE_REFERENCE_DOC` | (Default `docs/KNOWLEDGE_AND_PROCESS.md`) used when reporting KB sync status. |
| `ZITADEL_BASE_URL` / `ZITADEL_PROJECT_ID` | Required for Zitadel tools (defaults match local stack). |
| `ZITADEL_SERVICE_ACCOUNT_SECRET` | Name of the LocalStack secret containing machine-user PAT. |
| `DOCKER_HOST` | Socket path for Docker read-only tools (defaults to `/var/run/docker.sock`). |

---

## 4. Deployment Steps

1. **Set secrets** (see prerequisites).
2. **Rebuild & start the service**
   ```bash
   docker compose build mcp-server-gitlab
   docker compose up -d mcp-server-gitlab
   ```
3. **Restart Traefik** (new router `mcp.gitlab.ravenhelm.test`):
   ```bash
   cd ravenhelm-proxy
   docker compose -f docker-compose-traefik.yml restart traefik
   ```
4. **Health checks**
   ```bash
   curl -sk https://mcp.gitlab.ravenhelm.test/healthz
   # => {"status":"ok","service":"mcp-server-gitlab"}

   # Verify GitLab PAT auth from inside the container
   ./scripts/test-mcp-gitlab.sh
   # => {"status":"ok","user":{"username":"<pat_user>", ...}}
   ```

Logs:
```bash
docker compose logs -f mcp-server-gitlab
```

---

## 5. Available Tools (Phase 4A)

| MCP Tool | Description | Notes |
|----------|-------------|-------|
| `gitlab.projects.create` | Idempotent project creation in a group. | Returns status + web URL. |
| `gitlab.projects.add_webhook` | Create/update project webhooks. | Accepts event list + secret token. |
| `gitlab.runners.list` | Enumerate runners (filter by status/tags). | Used for audits & troubleshooting. |
| `gitlab.runners.pause` | Pause/resume a runner. | Useful for maintenance windows. |
| `knowledge.wiki.list_pages` | Read-only list of wiki pages. | Honors the “no direct wiki writes yet” rule. |
| `knowledge.docs.sync_status` | Reports manual sync requirements (docs ↔ wiki). | References `docs/KNOWLEDGE_AND_PROCESS.md`. |
| `zitadel.users.list_roles` | Fetch project role grants for a user. | Accepts `user_id` or `email`; uses service account PAT. |
| `zitadel.users.assign_roles` | Grant Zitadel project roles to a user. | Writes are audited via Loki; requires `role_keys`. |
| `zitadel.service_accounts.create` | Create a machine user + PAT and optionally assign roles. | Returns PAT token for the new service account. |
| `docker.containers.list` | List Docker containers (status, labels, etc.). | Read-only; socket mounted as `/var/run/docker.sock`. |
| `docker.containers.stats` | Retrieve CPU/memory stats for a container. | Accepts container ID or friendly name. |

Future phases will add:
- Runner registration + token storage in LocalStack.
- Knowledge-base MR creation to stage wiki updates.
- Additional tools (issues, pipelines) once scoped.

### 5.1 Zitadel Tooling

- Ensure the machine-user PAT stored in `ravenhelm/dev/zitadel/service_account` has `projectOwner` (or equivalent) rights in the Ravenhelm project.
- All Zitadel tools accept either a `user_id` or `email` selector. When both are provided, `user_id` wins.
- Example payloads:

```json
{
  "name": "zitadel.users.assign_roles",
  "arguments": {
    "email": "operator@ravenhelm.test",
    "role_keys": ["developer", "operator"]
  }
}
```

```json
{
  "name": "zitadel.service_accounts.create",
  "arguments": {
    "user_name": "norns-agent",
    "display_name": "Norns Automation",
    "role_keys": ["developer"]
  }
}
```

### 5.2 Docker Tooling

- The MCP container mounts `/var/run/docker.sock` from the host. Tools are intentionally read-only.
- Filtering options:
  - `status`: `running`, `exited`, etc.
  - `label`: e.g., `ravenhelm.service=grafana`.
  - `name`: substring match (`gitlab-sre`).
- Example requests:

```json
{
  "name": "docker.containers.list",
  "arguments": {
    "label": "ravenhelm.service=gitlab"
  }
}
```

```json
{
  "name": "docker.containers.stats",
  "arguments": {
    "container_id": "gitlab-sre-loki"
  }
}
```

---

## 6. Security & Access

1. **Ingress**: Traefik router `mcp.gitlab.ravenhelm.test` uses the `protected` middleware (`secure-headers` + oauth2-proxy forward auth). Only authenticated Zitadel users can reach the API.
2. **OAuth enforcement**: Every MCP call must include a Zitadel-issued bearer token. The service validates JWTs against the Zitadel JWKS endpoint and enforces the `mcp.gitlab.manage` scope (see [MCP Python SDK simple-auth example](https://github.com/modelcontextprotocol/python-sdk/tree/main/examples/servers/simple-auth) for reference).
3. **mTLS / SPIRE**:  
   - `mcp-gitlab-spiffe-helper` writes the service SVID into `/run/spire/certs` (mounted read-only into the container) and Uvicorn terminates HTTPS with that cert.  
   - Traefik now has its own helper (`traefik-spiffe-helper` in `ravenhelm-proxy/docker-compose-traefik.yml`) which writes a client SVID into `/run/spire/certs` inside the Traefik container.  
   - Traefik’s `serversTransports.mcp-gitlab-transport` trusts `certs/spire-bundle.pem` and presents `/run/spire/certs/svid.pem` when calling the backend, so `TLS_REQUIRE_CLIENT_CERT=true` can remain enabled in production.
4. **Secrets**: PATs retrieved via LocalStack Secrets Manager; no tokens are persisted in the image.
5. **Logging & Audit**: structlog outputs to Docker logs (collected by Alloy → Loki) and include `mcp_tool_call` entries (tool name, OAuth subject, scopes, result).
6. **Rate limiting**: Not enforced yet; rely on Traefik and future OpenFGA policies for per-tool RBAC.

### 6.1 Mutual TLS Rollout Procedure

1. **Export SPIRE bundle for Traefik** (run from repo root):
   ```bash
   docker run --rm -v hlidskjalf_mcp_gitlab_certs:/certs alpine \
     cat /certs/bundle.pem > ravenhelm-proxy/config/certs/spire-bundle.pem
   ```
2. **Deploy Traefik helper & mount certs**  
   - `ravenhelm-proxy/docker-compose-traefik.yml` now includes `traefik-spiffe-helper` plus a shared volume `traefik_spire_certs`.  
   - Traefik mounts that volume at `/run/spire/certs` and the CA bundle at `/certs/spire-bundle.pem`.
3. **Update Traefik transport** (`ravenhelm-proxy/dynamic.yml`):
   ```yaml
   serversTransports:
     mcp-gitlab-transport:
       tls:
         rootCAs:
           - /certs/spire-bundle.pem
         cert:
           certFile: /run/spire/certs/svid.pem
           keyFile: /run/spire/certs/key.pem
   ```
4. **Require client certs on MCP server**  
   - In `docker-compose.yml`: `TLS_REQUIRE_CLIENT_CERT=true`.  
   - Restart `mcp-gitlab-spiffe-helper`, `mcp-server-gitlab`, Traefik helper, and Traefik.
5. **Validate**
   ```bash
   # From a host (expects Zitadel auth -> 302/401)
   curl -kI https://mcp.gitlab.ravenhelm.test/healthz

   # From Traefik container (should succeed with 200 once bearer token supplied)
   docker exec ravenhelm-traefik \
     openssl s_client -connect mcp-server-gitlab:9400 \
       -CAfile /run/spire/certs/bundle.pem \
       -cert /run/spire/certs/svid.pem \
       -key /run/spire/certs/key.pem -brief
   ```

## 7. Security Best Practices & Audit Policy

The security posture follows [Model Context Protocol Security Best Practices](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices). Before promoting the MCP server to a shared environment, complete the checklist below:

1. **mTLS Verification**
   - [ ] `mcp-gitlab-spiffe-helper` healthy and writing to `/run/spire/certs`.
   - [ ] `TLS_REQUIRE_CLIENT_CERT=true` in production and clients (e.g., Traefik/Bifrost) present SVIDs issued by SPIRE.
   - [ ] Traefik `serversTransport` trusts `/certs/spire-bundle.pem` (no `insecureSkipVerify`).
2. **OAuth Scopes**
   - [ ] Zitadel application for MCP server advertises the `mcp.gitlab.manage` scope.
   - [ ] Bifrost/Norns runtime requests the scope and sends `Authorization: Bearer …` headers.
   - [ ] Audit logs (Loki) show `mcp_tool_call` entries with subject + scope for every invocation.
3. **Consent & Least Privilege**
   - [ ] MCP tokens are limited to per-agent scopes; do not reuse admin PATs inside clients.
   - [ ] Secrets in LocalStack contain only PATs strictly necessary for GitLab+wiki operations.
4. **Session & Transport Hardening**
   - [ ] Disable plaintext port 9400 exposure once mTLS is enforced (only HTTPS).
   - [ ] Rotate SPIFFE SVIDs on their normal TTL; verify cert renewal by watching helper logs.
5. **Change Control**
   - [ ] Record each deployment in the GitLab issue board/milestones (per project plan).
   - [ ] Runbooks and design docs updated with any new tools, scopes, or compliance requirements.

Document any deviations plus mitigations before turning the server on for shared workloads.

---

## 8. Troubleshooting

| Symptom | Checks |
|---------|--------|
| `401 Unauthorized` via curl | Ensure you’re accessing through Traefik (needs Zitadel auth). When testing locally, sign in via browser first and reuse cookies. |
| `GitLab auth failed` in logs | Secrets entry missing/incorrect – confirm `awslocal secretsmanager get-secret-value --secret-id ravenhelm/dev/gitlab/mcp_service`. |
| Traefik route not found | Verify `ravenhelm-proxy/dynamic.yml` contains `mcp-gitlab` router and service; restart Traefik. For mTLS, update `serversTransports` to trust the SPIRE CA. |
| Tools returning stale data | Service caches project handles. Restart container if GitLab metadata changed (e.g., renaming groups). |

---

## 9. Change Log

| Date | Change |
|------|--------|
| 2025-12-03 | Initial deployment (projects, runners, knowledge read-only). |

---

## References

- `docs/architecture/MCP_SERVER_DESIGN.md`
- `docker-compose.yml` (`mcp-server-gitlab`)
- `ravenhelm-proxy/dynamic.yml` (Traefik route)
- `localstack/init/init-aws.sh` (secret seeding)

