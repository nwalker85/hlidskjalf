# SELF-HEALING PIPELINE ARCHITECTURE

## Purpose

Define how Ravenhelm’s monitoring, alerting, and self-healing loop should operate across detection → routing → intelligence → action → notification layers, while aligning the current stack with SRE best practices. This document is the north star for the Phase 6 work items in `/Users/nwalker/Development/hlidskjalf/PROJECT_PLAN.md`.

## 1. Current-State Overview

| Layer | Components (per `/Users/nwalker/Development/hlidskjalf/docker-compose.yml`) | Notes |
|-------|-----------------------------------------------------------------------------|-------|
| Detection | Grafana Alloy (collector), Prometheus, Loki, Tempo, Docker health checks | Alloy scrapes Docker, forwards metrics to Prometheus, logs to Loki, traces to Tempo. No Autoheal watchdog yet. |
| Routing | Alertmanager (no downstream receiver configured), Grafana dashboards | Alert rules not yet defined for golden signals. Alertmanager currently only exposes `/api/v2/alerts`. |
| Intelligence | Bifrost Gateway + Norns agents (`hlidskjalf` LangGraph backend) | Bifrost consumes GitLab work-items; no alert ingestion path. MCP server provides GitLab/Zitadel/Docker tools. |
| Action | Manual restarts via MCP / docker CLI | No automated remediation catalogue; Docker API access limited to MCP server. |
| Notification | Telegram adapter in Bifrost | Slack adapter skeleton exists but is not wired. PagerDuty/email adapters pending. |

References:
- `/Users/nwalker/Development/hlidskjalf/observability/...`
- `docs/runbooks/RUNBOOK-007-observability-setup.md`
- `docs/runbooks/RUNBOOK-020-add-bifrost-adapter.md`
- `docs/runbooks/RUNBOOK-025-norns-work-queue.md`

## 2. Best-Practice Benchmarks

| Practice | Industry Guidance | Current Coverage | Gap / Action |
|----------|-------------------|------------------|--------------|
| SLO-driven alerting | Metrics cover golden signals (latency, errors, saturation, traffic) with multi-window, multi-burn alerts routed by severity. | Prometheus deployed but no alert rules. | Author `observability/prometheus/rules/self_heal.rules.yml` with the scaffolded alerts from `PROJECT_PLAN.md` and tie to Alertmanager. |
| Alert fan-out | Alertmanager routes to human + automation sink; dedup + grouping per service. | Alertmanager exists but no receivers configured. | Add Bifrost webhook receiver (mTLS via Traefik serversTransport) plus Slack/PagerDuty endpoints. |
| Ticket automation | Every Sev1/2 alert opens a tracking issue or updates the Ops board automatically. | GitLab work queue only processes manually labeled issues. | Extend Bifrost alert handler to create `workflow::triage` issues when auto-remediation fails. |
| Auto remediation guardrails | Automated actions must be idempotent, observable, and limited (max retries before human escalation). | MCP docker tools exist; no orchestrator. | Implement Norns “alert-handler” mission runbook + allow-list of MCP tools (restart container, scale service) mediated via SPIRE-authenticated MCP calls. |
| Audit logging | Incident bot posts a summary of actions + links to dashboards/logs. | `docs/NORNS_MISSION_LOG.md` manually updated. | Stream Bifrost alert handler events to Loki + append mission log entries programmatically. |
| ChatOps integration | Primary comms channel (Slack) receives alert cards, buttons to Ack/Snooze/Escalate. | Telegram only. Slack adapter skeleton unimplemented. | Finish Slack adapter, enforce Zitadel user mapping, and register slash commands for alert control. |

## 3. Target Self-Healing Flow

1. **Detection** – Alloy scrapes container metrics + Otel traces/logs; Prometheus evaluates alert rules every 30s.
2. **Routing** – Alertmanager groups by `{service, severity}` and sends JSON payloads to `https://bifrost.ravenhelm.test/api/alerts/ingest` (SPIFFE mTLS via Traefik `serversTransport`).
3. **Intelligence** – Bifrost normalizes alerts → publishes to `alerts.selfheal` (NATS/Redis queue). Norns alert-handler subscribes, enriches with Grafana/Tempo links, runs diagnostics via MCP tools (GitLab deploy history, Docker stats, Zitadel RBAC checks).
4. **Action** – Handler executes approved runbooks (restart container, recycle SPIRE helper, roll back env var) through MCP or Autoheal sidecar. If remediation fails thrice, create/update GitLab issue, escalate to Slack/PagerDuty.
5. **Notification** – Slack gateway posts threaded updates with `/ack` and `/handoff` commands; Telegram remains optional for backup; Bifrost writes all actions to Loki + mission log.

## 4. Implementation Roadmap (maps to Phase 6 tasks)

1. **Detection Enhancements**
   - Add Autoheal container (Docker events → `/metrics`). 
   - Create Prometheus rule files for the standard alerts in `PROJECT_PLAN.md`.
   - Ensure Alloy scrapes Autoheal metrics and forwards OTLP traces from hlidskjalf services (fix OTLP destination as part of Phase 4 warnings).
2. **Routing Improvements**
   - Update `observability/alertmanager/alertmanager.yml` with `bifrost` and `slack` receivers, using SPIRE mTLS when talking to Traefik.
   - Add GitLab webhooks for ticket automation backlog once receivers exist.
3. **Intelligence Layer**
   - Extend MCP server with remediation tools (already partially complete with Docker/Zitadel). Document usage in `docs/runbooks/RUNBOOK-023-mcp-gitlab-server.md`.
   - Define Norns “alert-handler” mission in `config/agent_registry.yaml` pointing to MCP credentials stored in LocalStack (`ravenhelm/dev/zitadel/norns_alerts`).
4. **Action & Notification**
   - Finalize Slack adapter (see Section 5) and expose `/webhook/slack` via Traefik + Zitadel forward auth.
   - Write RUNBOOK-008 (Alert Response) describing auto/manual decision tree.
   - Update `docs/NORNS_MISSION_LOG.md`/`docs/FINAL_ACCOMPLISHMENTS.md` whenever new remediation patterns are added.

## 5. Slack Gateway Prereqs

Slack integration must conform to these controls before enabling `SLACK_ENABLED=true` in `/Users/nwalker/Development/hlidskjalf/bifrost-gateway/docker-compose.yml`:

1. **Secrets Management**
   - Store `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` in LocalStack (`ravenhelm/dev/bifrost/slack_bot`).
   - Fetch via `src/secrets.py` at startup; never bake tokens into compose files.
2. **Zitadel Mapping**
   - Use Slack email → Zitadel user lookup to enforce `actor::norns` gating. Maintain allowlists via `SLACK_ALLOWED_USERS` and project roles in Zitadel.
3. **Webhook Security**
   - Implement signature verification in `SlackAdapter.verify_webhook`.
   - Require Traefik forward-auth (`oauth2-proxy`) for management endpoints, but allow Slack’s Events API path to bypass while still validating signatures.
4. **Alert UX**
   - Define message schema (summary, Grafana links, remediation buttons). Buttons should hit Bifrost `/api/alerts/actions` with Zitadel-issued JWTs.
5. **Runbooks**
   - Update `docs/runbooks/RUNBOOK-020-add-bifrost-adapter.md` with Slack-specific setup (bot scopes, Events subscription, `.env` overrides, Traefik labels).

## 6. Deliverables Checklist

- [ ] Prometheus rule files + Alertmanager receivers under `observability/`.
- [ ] Autoheal container service definition + RUNBOOK entry.
- [ ] Bifrost alert ingestion endpoint + Slack gateway.
- [ ] Norns alert-handler mission + remediation MCP tools.
- [ ] RUNBOOK-008 Alert Response and Slack adapter appendix in RUNBOOK-020.
- [ ] GitLab issues for remaining work tracked under Phase 6.

---

**Last updated:** 2025-12-04  
**Owner:** Norns Platform Team  

