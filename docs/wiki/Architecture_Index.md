# Architecture Index

Sourced from the Norns Documentation Orchestrator. This page will be mirrored into the GitLab wiki once we finalize the structure.

| Section | Description | Primary Sources |
|---------|-------------|-----------------|
| **Security Architecture** | Zero-trust SPIRE identity fabric, mTLS service mesh, Zitadel SSO, and layered encryption (storage, transport, application) | `PROJECT_PLAN.md`, `docs/architecture/SECURITY_HARDENING_PLAN.md`, `spire/init-spire.sh` |
| **Cognitive Infrastructure** | Dual-raven memory system: Huginn (NATS+Redis state), Muninn (Redpanda+PostgreSQL knowledge), domain-specific ontologies | `README.md`, `docker-compose.yml`, `hlidskjalf/src/memory/` |
| **Event-Driven Coordination** | Multi-agent orchestration via Kafka topics, real-time state synchronization through NATS JetStream | `docker-compose.yml`, `config/agent_registry.yaml`, `PROJECT_PLAN.md` |
| **Service Mesh & Routing** | Traefik edge proxy with automatic service discovery, network segmentation, zero-downtime deployments | `docs/architecture/TRAEFIK_MIGRATION_PLAN.md`, `config/port_registry.yaml`, `docker-compose.yml` |
| **Identity & Access Management** | Zitadel OIDC for human users, OAuth 2.1 for machine-to-machine, service accounts, role-based access control | `PROJECT_PLAN.md`, `docs/runbooks/RUNBOOK-006-zitadel-sso.md`, `scripts/bootstrap-zitadel.sh` |
| **Secrets Management** | LocalStack Secrets Manager for dev/prod parity, S3 artifact storage, dynamic credential rotation | `hlidskjalf/src/core/secrets.py`, `scripts/rotate-secrets.sh`, `docs/runbooks/RUNBOOK-010-secret-rotation.md` |
| **Observability Pipeline** | OTEL-native tracing, Grafana observability stack, LLM-specific monitoring (LangFuse), cost tracking | `docker-compose.yml`, `docs/runbooks/RUNBOOK-007-observability-setup.md`, `PROJECT_PLAN.md` |
| **Voice & Real-Time Systems** | LiveKit WebRTC infrastructure, bidirectional audio streaming, external service integration (Deepgram, ElevenLabs) | `docs/runbooks/RUNBOOK-022-configure-voice-agent.md`, `config/port_registry.yaml`, `README.md` |
| **Platform Standardization** | Unified user model (ravenhelm:1001:1001), Docker network policies, port allocation registry, file ownership patterns | `scripts/init-platform.sh`, `config/port_registry.yaml`, `docs/runbooks/RUNBOOK-005-file-ownership-permissions.md` |
| **Project Templates & Workflows** | Ravenmaskos boilerplate (FastAPI+Next.js), GitLab CI/CD pipelines, Kubernetes deployment manifests | `templates/ravenmaskos/`, `PROJECT_PLAN.md`, `docs/architecture/REORGANIZATION.md` |

## Migration TODOs

1. **Complete SPIRE workload registration** – Execute `./spire/init-spire.sh bootstrap` and register remaining services in `docker-compose.yml` with SPIFFE IDs referenced in `PROJECT_PLAN.md` Phase 0 checklist.
2. **Migrate from nginx to Traefik** – Implement autodiscovery routing using `docs/architecture/TRAEFIK_MIGRATION_PLAN.md` and update all service labels/entrypoints.
3. **Deploy production-ready Zitadel** – Run `scripts/bootstrap-zitadel.sh` and configure SSO for every service listed in `PROJECT_PLAN.md` Phase 1.
4. **Implement secrets rotation** – Move plaintext credentials from `.env` to LocalStack Secrets Manager using `scripts/rotate-secrets.sh` plus `docs/runbooks/RUNBOOK-010-secret-rotation.md`.
5. **Standardize file ownership** – Apply the `ravenhelm:1001:1001` model via `scripts/init-platform.sh` and confirm mounts per `docs/runbooks/RUNBOOK-005-file-ownership-permissions.md`.
6. **Establish MCP security** – Protect all MCP servers with OAuth 2.1 as outlined in Phase 4 of `PROJECT_PLAN.md`.

