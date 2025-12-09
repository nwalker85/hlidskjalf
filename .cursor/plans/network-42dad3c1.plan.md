---
name: Monitoring & Self-Healing Readiness Plan
overview: ""
todos:
  - id: ff7a5258-71b8-4977-b4f0-80e6378f639d
    content: Survey docs directory structure
    status: pending
  - id: 62bb9c35-8385-47ff-8b37-ddcdff1256e7
    content: Review each markdown doc for issues
    status: pending
  - id: 929415cd-ed4d-42fa-a7eb-093cfe90a7c3
    content: Summarize findings or confirm review
    status: pending
  - id: e3fb9350-c1c4-4cb9-882f-1443aaa059e7
    content: Audit observability stack + docs for Phase6 gaps
    status: pending
  - id: 79478c56-dfa0-4054-821f-f635c34ceb3c
    content: Document best practices vs current-state deltas
    status: pending
  - id: d00dfedc-137e-4402-b4ab-0752b988e35d
    content: Define Slack adapter config + changes for Bifrost
    status: pending
  - id: 12c91c5c-384a-41f7-b9ad-7ec8f7b97628
    content: Summarize gaps, deliverables, and next steps
    status: pending
---

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