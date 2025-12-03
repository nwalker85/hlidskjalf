# Operations

- **Runbooks:** See [Runbook Catalog](Runbook_Catalog.md) for categorized procedures.
- **Checklists:** Use `docs/runbooks/RUNBOOK-001` through `RUNBOOK-022` before promoting changes.
- **Observability:** Follow `docs/runbooks/RUNBOOK-007-observability-setup.md` to keep Grafana dashboards + alerting aligned with deployments.
- **Runbook Maintenance:** Quarterly validate each runbook in a clean environment and capture lessons learned in `docs/LESSONS_LEARNED.md`.
- **Automation Backlog:** Implement the runbook catalog sync pipeline + skills catalog job (see Operations Board).

## Automation Helpers
- `./scripts/sync_wiki.sh` — pushes `docs/wiki/*` into the GitLab wiki (requires `GITLAB_TOKEN`).
- `./scripts/ops_board.py` — list/create/move issues on the Operations Board without leaving the terminal.

Set `GITLAB_TOKEN` before running either script so they can authenticate against `gitlab.ravenhelm.test`.

## Automation Helpers
- `./scripts/sync_wiki.sh` — pushes `docs/wiki/*` into the GitLab wiki (requires `GITLAB_TOKEN`).
- `./scripts/ops_board.py` — list/create/move issues on the Operations Board without leaving the terminal.

Set `GITLAB_TOKEN` before running either script so they can authenticate against `gitlab.ravenhelm.test`.

