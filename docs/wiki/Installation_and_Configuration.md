# Installation & Configuration

## Environment Bootstrap
1. **Certificates:** `docs/runbooks/RUNBOOK-003-generate-certificates.md`
2. **Traefik & DNS:** `docs/runbooks/RUNBOOK-002-add-traefik-domain.md`, `docs/runbooks/ravenhelm-traefik-autodiscovery.md`
3. **SPIRE:** `docs/runbooks/RUNBOOK-004-spire-management.md`
4. **Docker Services:** `docs/runbooks/RUNBOOK-001-deploy-docker-service.md`

## Configuration Registry
- Ports & domains: `config/port_registry.yaml`
- Docker compose overlays: `docker-compose.yml`, `docker-compose-updated.yml`
- Environment variables: `.env`, `.langgraph_api`, `.zitadel-apps.env`

## Pending Work
- Document AWS/LocalStack setup (Secrets Manager, S3, Terraform state).
- Publish Terraform instructions from `templates/platform-template/terraform`.
- Add step-by-step checklists for dev/staging/prod promotion.

