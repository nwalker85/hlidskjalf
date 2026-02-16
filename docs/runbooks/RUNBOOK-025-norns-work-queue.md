# RUNBOOK-025: Norns Work Queue & GitLab Integration

> _“Threads of fate now begin in GitLab. Only when a story bears the rune `actor::norns` do the sisters pick up the loom.”_

## 1. Purpose

Provide a repeatable process for routing GitLab issues to the Norns AI agents via Bifrost Gateway, with webhook delivery, polling fallback, observability, and audit trails.

## 2. Prerequisites

| Component | Requirement |
| --- | --- |
| GitLab | Project hosted at `gitlab.ravenhelm.test`, PAT with API scope (stored in `ravenhelm/dev/gitlab/mcp_service`). |
| Bifrost Gateway | Running on `bifrost-gateway` container (port 8050, Traefik route `norns.ravenhelm.test/api/work-items`). |
| Secrets | LocalStack initialized with `ravenhelm/dev/gitlab/webhook/norns` secret (32-byte token). |
| Labels | Scoped labels `type::*`, `workflow::*`, `area::*`, plus new `actor::norns`. |
| Boards | “Norns Queue” board filtered to `labels=actor::norns` with workflow lists. |

## 3. Workflow Overview

1. Product owner creates/curates GitLab issue, applies:
   - `actor::norns`
   - `workflow::ready`
   - Relevant `type::` + epic label
2. GitLab webhook fires to `https://norns.ravenhelm.test/api/work-items`.
3. Bifrost validates `X-Gitlab-Token`, fetches issue details via GitLab API, enqueues task, comments back (“Norns acknowledged…”), transitions labels to `workflow::in_progress`, and notifies the LangGraph backend.
4. Prometheus tracks queue depth, throughput, and last-processed timestamp; Grafana dashboard shows live KPIs.
5. Optional poller reconciles every 3 minutes to protect against missed webhooks.

## 4. Configuration Steps

### 4.1 Reserve labels & board

1. Create label `actor::norns` (color `#e83e8c`).
2. Ensure `workflow::ready`, `workflow::in_progress`, `workflow::blocked`, `workflow::done` exist.
3. Create board “Norns Queue” (project → Issue Boards) filtered to `actor::norns`. Add lists for the workflow labels.

### 4.2 Deploy Bifrost work queue

Bifrost configuration lives in `bifrost-gateway/docker-compose.yml`. Key env vars:

```yaml
      - GITLAB_BASE_URL=http://gitlab-sre-gitlab
      - GITLAB_PROJECT_ID=2
      - GITLAB_PAT_SECRET_NAME=ravenhelm/dev/gitlab/mcp_service
      - GITLAB_WEBHOOK_SECRET_NAME=ravenhelm/dev/gitlab/webhook/norns
      - AWS_ENDPOINT_URL=http://gitlab-sre-localstack:4566
      - AWS_REGION=us-east-1
```

Redeploy Bifrost:

```bash
cd bifrost-gateway
docker compose up -d --build
```

This exposes `/api/work-items` (FastAPI), starts `WorkItemProcessor`, and optional `WorkItemPoller`.

### 4.3 Traefik routing

`ravenhelm-proxy/dynamic.yml` routes `Host(norns.ravenhelm.test) && PathPrefix(/api/work-items)` to the Bifrost service (`norns-workqueue-svc` → host `8050`). All other paths continue to LangGraph.

### 4.4 GitLab webhook

1. Ensure GitLab allows local hooks (already set via `gitlab_rails['allow_requests_to_local_network_from_web_hooks_and_services'] = true`).
2. Add `/etc/hosts` entry for `norns.ravenhelm.test` pointing to `host-gateway`.
3. Register webhook (replace token with secret from `ravenhelm/dev/gitlab/webhook/norns`):

```bash
curl -sk --request POST \
  --header "PRIVATE-TOKEN: ${GITLAB_PAT}" \
  --data "url=https://norns.ravenhelm.test/api/work-items" \
  --data "issues_events=true" \
  --data "enable_ssl_verification=false" \
  --data "token=${WEBHOOK_SECRET}" \
  https://gitlab.ravenhelm.test/api/v4/projects/2/hooks
```

4. Verify delivery under **Settings ▸ Webhooks**.

### 4.5 Polling fallback (optional)

`WorkItemPoller` queries `/issues?labels=actor::norns,workflow::ready` every 180s. No extra setup; ensure GitLab PAT is valid.

## 5. Observability & KPIs

Prometheus (`observability/prometheus/prometheus.yml`) scrapes `bifrost-gateway:8050/metrics`. Key metrics:

| Metric | Meaning |
| --- | --- |
| `norns_work_queue_depth` | Current queue size. |
| `norns_work_items_received_total{source}` | Webhook vs poller ingestion. |
| `norns_work_items_processed_total{status}` | Success/failure counts. |
| `norns_work_item_last_processed_timestamp` | Unix timestamp of last completion. |

Grafana dashboard `norns-ai` now includes queue depth, minutes since last completion, and throughput panels with alerts for stuck items.

## 6. Runbook Tasks

| Task | Steps |
| --- | --- |
| Manually enqueue work | Apply `actor::norns` + `workflow::ready`; confirm board updates. |
| Pause queue | Remove label or scale Bifrost to zero; webhook returns 503. |
| Replay missed items | Use poller logs (`bifrost-gateway` container) or run manual script: `curl https://gitlab.../issues?labels=actor::norns,workflow::ready`. |
| Rotate secrets | Update LocalStack secrets (`ravenhelm/dev/gitlab/...`), restart Bifrost, recreate webhook token in GitLab. |

## 7. Troubleshooting

| Symptom | Resolution |
| --- | --- |
| Webhook 403 | Token mismatch. Rotate `ravenhelm/dev/gitlab/webhook/norns`, update GitLab hook. |
| Bifrost logs `gitlab_mcp_token_missing` | Ensure PAT secret exists and Bifrost has LocalStack connectivity. |
| Queue depth never decreases | Check LangGraph health, confirm Bifrost can reach `hlidskjalf` backend. |
| Grafana panels empty | Verify Prometheus job `bifrost-gateway` scraping; restart Prometheus if config updated. |
| GitLab “Invalid url given” | Confirm `/etc/hosts` entry for `norns.ravenhelm.test` and allow-local-network flags set. |

## 8. References

- `bifrost-gateway/src/work_items.py` — processor, poller, metrics.
- `docs/process/AGILE_OPERATING_MODEL.md` — workflow labels & viewing modes.
- `observability/grafana/.../norns-ai.json` — dashboard panels.
- `observability/prometheus/prometheus.yml` — scrape config.

