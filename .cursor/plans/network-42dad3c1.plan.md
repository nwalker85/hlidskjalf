<!-- 42dad3c1-1712-47ec-a620-df29d72447d0 2a6cc873-7002-4cc8-8e56-1529a15166b6 -->
# Monitoring & Self-Healing Readiness Plan

## 1. Current-State Audit

- Review the observability stack definitions in [`observability/`](../Users/nwalker/Development/hlidskjalf/observability/) along with `docker-compose.yml`/`docker-compose-backup.yml` to map Prometheus, Alertmanager, Grafana Alloy, Loki, Tempo, Docker health checks, and Autoheal coverage.
- Re-read the monitoring-related runbooks (`docs/runbooks/RUNBOOK-004/005/007/025`), `docs/wiki/Operations.md`, and Phase 6 items in [`PROJECT_PLAN.md`](../Users/nwalker/Development/hlidskjalf/PROJECT_PLAN.md) to capture declared workflows, open gaps, and existing ticketing/notification hooks (Bifrost, Norns, GitLab automation).
- Summarize the findings (per layer: detection, routing, intelligence, remediation, notification) in notes for later documentation.

## 2. Best-Practices Benchmark

- Compile a concise reference of industry best practices for automated monitoring/alerting/self-healing (e.g., SLO-driven Prometheus rules, Alertmanager routing, automated remediation safeguards, ticketing/audit requirements).
- Capture how those best practices map to Ravenhelm constraints (Traefik ingress, SPIRE identities, Zitadel auth, LocalStack secrets, Bifrost messaging) in a new architecture note [`docs/architecture/SELF_HEALING_PIPELINE.md`](../Users/nwalker/Development/hlidskjalf/docs/architecture/SELF_HEALING_PIPELINE.md).
- Update `docs/LESSONS_LEARNED.md` or the relevant runbook if the audit discovers material gaps or new procedures.

## 3. Slack Gateway Readiness

- Inspect the existing Bifrost adapter scaffolding (`bifrost-gateway/src/adapters/`, `src/main.py`, `README.md`) to understand how Telegram is wired today and what Slack support already exists.
- Define the configuration contract for Slack (env vars, secrets names in LocalStack, Zitadel OAuth requirements, Traefik route updates) and document it in `docs/runbooks/RUNBOOK-021-add-bifrost-ai-backend.md` or a new Slack-specific runbook entry.
- Outline the concrete code/config changes needed to enable Slack (adapter registration, webhook endpoint, signing secret validation, message routing to Norns/MCP) without implementing them yet.

## 4. Deliverables & Next Steps

- Produce a written gap analysis + recommendations list that ties Phase 6 tasks to actionable steps (Prometheus rules, Autoheal container, Alertmanager→Bifrost, Norns alert agent, ticketing automation).
- Identify any prerequisite work (e.g., secrets provisioning, SPIRE SVID updates) and add them to `PROJECT_PLAN.md`/GitLab issue backlog once approved.
- Present the final plan + Slack adapter readiness notes so we can proceed with implementation after approval.

### To-dos

- [ ] Survey docs directory structure
- [ ] Review each markdown doc for issues
- [ ] Summarize findings or confirm review
- [ ] Audit observability stack + docs for Phase6 gaps
- [ ] Document best practices vs current-state deltas
- [ ] Define Slack adapter config + changes for Bifrost
- [ ] Summarize gaps, deliverables, and next steps