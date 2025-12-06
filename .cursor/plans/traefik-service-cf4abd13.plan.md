<!-- cf4abd13-cb2a-4d6c-908e-68ecd8dd2d3c 8fdc5185-5a35-4ff7-81e6-246cda04a622 -->
# Rule & Knowledge Strategy

## Objectives

- Capture the critical project knowledge (architecture, secrets, workflows, runbooks) as Cursor rules so future sessions start with consistent guidance.
- Determine which instructions belong in project-wide rules vs. nested rules vs. AGENTS.md.
- Ensure rules point to living documentation (runbooks, design docs) instead of duplicating large content.

## Implementation Steps

1. **Inventory existing knowledge sources**  

- Categorize docs (architecture, security, observability, MCP, service onboarding) and list which ones should be referenced by rules.  
- Identify sensitive info (secrets, tokens) and replace with pointers to LocalStack/Vault workflows.

2. **Define rule hierarchy & scope**  

- Decide the top-level instructions for `.cursor/rules` (communication style, high-level architecture, secrets handling).  
- Plan nested rule directories (e.g., `services/mcp-server-gitlab/.cursor/rules`, `ravenhelm-proxy/.cursor/rules`) for domain-specific guidance.  
- Decide where AGENTS.md can provide quick-start instructions (root + submodules).

3. **Author or update rules**  

- Create concise MDC files referencing docs/runbooks/port registry, focusing on actionable steps (e.g., “See RUNBOOK-024 for adding services”).  
- Include sections for secrets retrieval (LocalStack script paths), design overviews (from `PROJECT_PLAN.md`, `MCP_SERVER_DESIGN.md`), and process checklists.  
- Ensure AGENTS.md (if used) summarizes operating procedures without duplicating rule content.

4. **Review & iterate**  

- Validate that rules render correctly in Cursor (no >500 lines, actionable language).  
- Share with the team, collect feedback, and adjust scope/wording. That way the rules remain accurate as docs evolve.

### To-dos

- [ ] Configure Hliðskjálf UI OIDC (SSO login)
- [ ] Configure LangFuse OIDC
- [ ] Create Norns service account in Zitadel
- [ ] Create RUNBOOK-006 for Zitadel
- [ ] Update PROJECT_PLAN.md with completion status
- [ ] Create Grafana Alloy configuration
- [ ] Add Alloy to docker-compose.yml
- [ ] Configure Loki for log ingestion
- [ ] Configure Loki datasource in Grafana
- [ ] Test log collection and visualization
- [ ] Fix redpanda-console port conflict (8080 -> 18082)
- [ ] Add missing routes: gitlab, loki, otel, nats-monitor, spire, livekit
- [ ] Remove redundant nginx proxy services from docker-compose.yml
- [ ] Test all routes through Traefik
- [ ] Add LocalStack auth token for persistence
- [ ] Expand LocalStack init script with all secrets
- [ ] Create Python SecretsClient for AWS Secrets Manager
- [ ] Configure S3 buckets (artifacts, backups, logs, terraform)
- [ ] Enable Redis AUTH with password from Secrets Manager
- [ ] Store PostgreSQL credentials in Secrets Manager
- [ ] Create database backup-to-S3 script
- [ ] Create RUNBOOK-010 for secret rotation
- [ ] Update PROJECT_PLAN.md with Phase 2 completion
- [ ] Add LocalStack auth token for persistence
- [ ] Expand LocalStack init script with all secrets
- [ ] Create Python SecretsClient for AWS Secrets Manager
- [ ] Configure S3 buckets (artifacts, backups, logs, terraform)
- [ ] Enable Redis AUTH with password from Secrets Manager
- [ ] Store PostgreSQL credentials in Secrets Manager
- [ ] Create database backup-to-S3 script
- [ ] Create RUNBOOK-010 for secret rotation
- [ ] Update PROJECT_PLAN.md with Phase 2 completion
- [ ] Create Zitadel OIDC app for oauth2-proxy
- [ ] Deploy oauth2-proxy with Zitadel configuration
- [ ] Configure Traefik forwardAuth middleware
- [ ] Apply auth middleware to protected routes
- [ ] Test zero-trust access for all services
- [ ] Update PROJECT_PLAN.md with Phase 3 completion
- [ ] Configure Hliðskjálf UI OIDC (SSO login)
- [ ] Configure LangFuse OIDC
- [ ] Create Norns service account in Zitadel
- [ ] Create RUNBOOK-006 for Zitadel
- [ ] Update PROJECT_PLAN.md with completion status
- [ ] Create Grafana Alloy configuration
- [ ] Add Alloy to docker-compose.yml
- [ ] Configure Loki for log ingestion
- [ ] Configure Loki datasource in Grafana
- [ ] Test log collection and visualization
- [ ] Fix redpanda-console port conflict (8080 -> 18082)
- [ ] Add missing routes: gitlab, loki, otel, nats-monitor, spire, livekit
- [ ] Remove redundant nginx proxy services from docker-compose.yml
- [ ] Test all routes through Traefik
- [ ] Add LocalStack auth token for persistence
- [ ] Expand LocalStack init script with all secrets
- [ ] Create Python SecretsClient for AWS Secrets Manager
- [ ] Configure S3 buckets (artifacts, backups, logs, terraform)
- [ ] Enable Redis AUTH with password from Secrets Manager
- [ ] Store PostgreSQL credentials in Secrets Manager
- [ ] Create database backup-to-S3 script
- [ ] Create RUNBOOK-010 for secret rotation
- [ ] Update PROJECT_PLAN.md with Phase 2 completion
- [ ] Add mcp-server-gitlab service + routing
- [ ] Implement MCP GitLab + knowledge tools
- [ ] Wire secrets/config & docs updates
- [ ] Traefik trusts SPIRE CA for MCP backend
- [ ] Traefik presents SPIRE client cert
- [ ] Set MCP server TLS_REQUIRE_CLIENT_CERT
- [ ] Doc+verify mutual TLS rollout
- [ ] Configure Hliðskjálf UI OIDC (SSO login)
- [ ] Configure LangFuse OIDC
- [ ] Create Norns service account in Zitadel
- [ ] Create RUNBOOK-006 for Zitadel
- [ ] Update PROJECT_PLAN.md with completion status
- [ ] Create Grafana Alloy configuration
- [ ] Add Alloy to docker-compose.yml
- [ ] Configure Loki for log ingestion
- [ ] Configure Loki datasource in Grafana
- [ ] Test log collection and visualization
- [ ] Fix redpanda-console port conflict (8080 -> 18082)
- [ ] Add missing routes: gitlab, loki, otel, nats-monitor, spire, livekit
- [ ] Remove redundant nginx proxy services from docker-compose.yml
- [ ] Test all routes through Traefik
- [ ] Add LocalStack auth token for persistence
- [ ] Expand LocalStack init script with all secrets
- [ ] Create Python SecretsClient for AWS Secrets Manager
- [ ] Configure S3 buckets (artifacts, backups, logs, terraform)
- [ ] Enable Redis AUTH with password from Secrets Manager
- [ ] Store PostgreSQL credentials in Secrets Manager
- [ ] Create database backup-to-S3 script
- [ ] Create RUNBOOK-010 for secret rotation
- [ ] Update PROJECT_PLAN.md with Phase 2 completion
- [ ] Add LocalStack auth token for persistence
- [ ] Expand LocalStack init script with all secrets
- [ ] Create Python SecretsClient for AWS Secrets Manager
- [ ] Configure S3 buckets (artifacts, backups, logs, terraform)
- [ ] Enable Redis AUTH with password from Secrets Manager
- [ ] Store PostgreSQL credentials in Secrets Manager
- [ ] Create database backup-to-S3 script
- [ ] Create RUNBOOK-010 for secret rotation
- [ ] Update PROJECT_PLAN.md with Phase 2 completion
- [ ] Create Zitadel OIDC app for oauth2-proxy
- [ ] Deploy oauth2-proxy with Zitadel configuration
- [ ] Configure Traefik forwardAuth middleware
- [ ] Apply auth middleware to protected routes
- [ ] Test zero-trust access for all services
- [ ] Update PROJECT_PLAN.md with Phase 3 completion
- [ ] Configure Hliðskjálf UI OIDC (SSO login)
- [ ] Configure LangFuse OIDC
- [ ] Create Norns service account in Zitadel
- [ ] Create RUNBOOK-006 for Zitadel
- [ ] Update PROJECT_PLAN.md with completion status
- [ ] Create Grafana Alloy configuration
- [ ] Add Alloy to docker-compose.yml
- [ ] Configure Loki for log ingestion
- [ ] Configure Loki datasource in Grafana
- [ ] Test log collection and visualization
- [ ] Fix redpanda-console port conflict (8080 -> 18082)
- [ ] Add missing routes: gitlab, loki, otel, nats-monitor, spire, livekit
- [ ] Remove redundant nginx proxy services from docker-compose.yml
- [ ] Test all routes through Traefik
- [ ] Add LocalStack auth token for persistence
- [ ] Expand LocalStack init script with all secrets
- [ ] Create Python SecretsClient for AWS Secrets Manager
- [ ] Configure S3 buckets (artifacts, backups, logs, terraform)
- [ ] Enable Redis AUTH with password from Secrets Manager
- [ ] Store PostgreSQL credentials in Secrets Manager
- [ ] Create database backup-to-S3 script
- [ ] Create RUNBOOK-010 for secret rotation
- [ ] Update PROJECT_PLAN.md with Phase 2 completion