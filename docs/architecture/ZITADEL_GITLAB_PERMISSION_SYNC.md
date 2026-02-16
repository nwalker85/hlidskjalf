# Zitadel → GitLab Permission Sync Architecture

## 1. Problem Statement & Objectives

GitLab currently relies on Zitadel for SSO, but authorization is still handled manually inside GitLab. We need an automated mechanism that:

1. Treats **Zitadel as the sole source of truth** for human and machine roles.
2. **Maps Zitadel roles/groups to GitLab access levels** (Owner, Maintainer, Developer, Reporter, Guest) and keeps them in sync.
3. **Prevents privilege drift** by revoking GitLab access as soon as the corresponding Zitadel role is removed.
4. Provides **verifiable audit trails** (logs + events) for every change.
5. Runs with the **least possible privilege** and fails safe (no role grant if anything looks suspicious).

## 2. Scope & Assumptions

- Covers **human users and service accounts** that authenticate via Zitadel.
- Applies to the **Ravenhelm GitLab group/project** only (ID=3 / project ID=2). Future expansion should generalize the mapping.
- Secrets (Zitadel service account token, GitLab PAT) live in **LocalStack Secrets Manager** and are fetched at runtime.
- The agent runs inside the **langgraph/Norns** stack (Docker container) and gets a SPIRE identity for mutual TLS when calling internal services.
- **Out of scope** for this iteration:
  - MCP OAuth enforcement (handled by another agent).
  - SCIM provisioning (GitLab CE lacks SCIM server; we are using REST APIs instead).

## 3. Threat Model

| Threat | Impact | Mitigation |
|--------|--------|------------|
| Compromised sync agent token | Unauthorized GitLab changes | Store GitLab PAT in Secrets Manager, limit scope to group/project, rotate regularly, restrict network egress. |
| API replay/DoS | Stuck state or privilege escalation | Idempotent operations (check before update), exponential backoff, rate limiting, health alerts. |
| Stale data (missed revocation) | Former user retains access | Poll + webhook combination, fail-safe mode: disable sync if last successful run exceeds SLA (alert). |
| Mapping misconfiguration | Incorrect role assignments | Role-mapping YAML checked into repo, requires PR review, dry-run mode before enforcement. |
| Insider abuse | Manual change bypassing sync | Sync runs hourly + on webhook; reverses unauthorized GitLab changes and logs them. |

## 4. Data Flows & APIs

### 4.1 Zitadel → Sync Agent
- **Polling**: Use the Management API (`/management/v1/projects/{projectId}/grants`) to list user grants per project role. Requires service account token with `Project Grant Manager` scope.
- **Webhook (optional)**: Configure Zitadel audit log webhook to publish grant change events to NATS (`zitadel.grants.changed`). Sync agent consumes for faster reaction.

### 4.2 Sync Agent → GitLab
- GitLab REST API:
  - `GET /groups/{id}/members` to fetch current role assignments.
  - `POST /groups/{id}/members` / `DELETE /groups/{id}/members/{user_id}` to add/remove.
  - `PUT /groups/{id}/members/{user_id}` to change access level.
- Authentication: PAT with `api` scope, stored in Secrets Manager under `saaa/dev/gitlab_permission_sync_token`.

### 4.3 State & Audit
- **State cache**: Lightweight SQLite or Redis set keyed by `zitadel_user_id -> checksum` to detect changes since last sync.
- **Audit events**: Emit CloudEvents into Kafka topic `audit.permission_sync` and forward to Loki (for compliance evidence).

## 5. Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                      Zitadel Permission Sync Agent                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  1. Fetch secrets (Zitadel SA token, GitLab PAT) from SecretsMgr    │
│  2. Poll Zitadel project grants (or consume webhook events)        │
│  3. Normalize mapping via mapping.yaml                             │
│  4. Compare with GitLab memberships (cached state)                 │
│  5. Apply changes via GitLab API (add/update/remove)               │
│  6. Emit audit events + metrics                                    │
│                                                                    │
└──────────────┬──────────────────────────────────┬──────────────────┘
               │                                  │
        Secrets Manager                       Kafka/Loki
```

### Component Notes
- **Config** (`config/permission-sync/mapping.yaml`):
  ```yaml
  roles:
    admin:
      gitlab_access_level: 50   # Owner
    developer:
      gitlab_access_level: 30   # Developer
    operator:
      gitlab_access_level: 20   # Reporter
    viewer:
      gitlab_access_level: 10   # Guest
  service_accounts:
    skuld:
      access_level: 50
  ```
- **Deployment**: Sidecar container or Norns subagent job with its own cron schedule (every 15 minutes) plus webhook handler for near-real-time sync.
- **Observability**: Prometheus metrics (`permission_sync_runs_total`, `permission_sync_errors_total`, `permission_sync_last_success_timestamp`) and Grafana panel under Operations dashboard.

## 6. Workflows

### 6.1 Bootstrap Sync
1. Run agent in `--dry-run` mode to compute diff without applying.
2. Review report, approve mapping.
3. Run with `--apply` to enforce, log every change.

### 6.2 Incremental Sync
1. On schedule/webhook, fetch new grants from Zitadel.
2. For each user:
   - If mapping differences found → update GitLab membership.
   - If user no longer has roles → remove from GitLab group.
3. Emit CloudEvent per change and append to audit log.

### 6.3 Failure Handling
- If GitLab API returns 4xx/5xx → retry with backoff, after N failures escalate (Alertmanager notification).
- If Zitadel API unreachable → pause sync, alert, do not grant new access.
- If mapping file invalid → abort with alert.

## 7. Security Controls
- **Secrets**: retrieved at runtime, not stored on disk. Use SPIRE SVID + mTLS when talking to Secrets Manager and internal Kafka.
- **Least Privilege**:
  - Zitadel service account limited to `Project Grant:Read`.
  - GitLab PAT limited to specific group/project.
- **Code Signing / Supply Chain**:
  - Container image built via GitLab CI, signed, and deployed only via known pipeline.
  - Hash of mapping file logged each run.
- **Auditability**:
  - Every change includes `who/when/why` metadata (Zitadel event ID, GitLab user ID, action).
  - Logs forwarded to Loki and retained 7 years (per compliance plan).

## 8. Deliverables & Rollout

| Deliverable | Description | Owner |
|-------------|-------------|-------|
| `docs/architecture/ZITADEL_GITLAB_PERMISSION_SYNC.md` | THIS DOCUMENT | Platform |
| `config/permission-sync/mapping.yaml` | Role → access mapping | Platform |
| `services/permission-sync` | Code (FastAPI or Python worker) + Dockerfile + CI pipeline | Engineering |
| RUNBOOK-0XX | Ops runbook covering deployment, monitoring, rollback | SRE |
| Grafana panel | Dashboard showing sync health | Observability |
| GitLab issues | Track implementation, dry-run, go-live | PM |

### Rollout Plan
1. **Phase A – Dry Run**: implement agent, run with `--dry-run`, compare output with current GitLab members, adjust mapping.
2. **Phase B – Monitored Enforce**: enable `--apply`, watch logs/metrics for at least 48h, double-check for unintended removals.
3. **Phase C – Steady State**: Add webhook for immediate sync, integrate alerts (Alertmanager) if sync stale > 30m.
4. **Phase D – Enhancement**: Extend to other services (LangFuse role mapping, Redpanda console) once GitLab workflow proven.

## 9. Follow-Up Actions
- [ ] Provision dedicated Zitadel service account with `Project Grant Manager` scope and store token in Secrets Manager.
- [ ] Create GitLab PAT for `ravenhelm/hlidskjalf` group, scoped to membership APIs, store securely.
+- [ ] Draft `RUNBOOK-0XX-permission-sync.md` describing deployment + incident handling.
- [ ] Add issues to Operations Board reflecting Dry Run, Enforce, Monitoring tasks (status labels accordingly).
- [ ] Update `PROJECT_PLAN.md` Phase 4 once implementation complete.

