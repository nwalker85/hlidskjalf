# Projects

## Active Initiatives
| Project | Description | Links |
|---------|-------------|-------|
| **Norns** | LangGraph-based multi-agent system with subagent swarm (file management, netops, security, observability, SSO, schema, cost, risk, governance, PM). | Repo: `hlidskjalf/src/norns/`, Wiki: [Architecture Index](Architecture_Index.md) |
| **GitLab Platform Template** | Opinionated FastAPI + Next.js starter with Terraform/IaC, CI/CD stages, runbooks, and voice integrations. | `templates/platform-template/README.md` |
| **RavenmaskOS** | Enterprise reference implementation (authz, cost tracking, voice stack). Used for customer demos. | `templates/ravenmaskos/README.md` |
| **Voice / LiveKit Stack** | LiveKit, Bifrost, Deepgram, ElevenLabs integrations for realtime agents. | `docs/runbooks/voice-webrtc.md`, `RUNBOOK-020/021/022` |

## Standard Project Checklist
1. **Service Registration:** Reserve ports via `config/port_registry.yaml` and register in `PROJECT_PLAN.md`.
2. **OIDC Integration:** Follow `docs/runbooks/RUNBOOK-006-zitadel-sso.md` for Zitadel scopes + secrets.
3. **Observability:** Ensure Alloy collector configs exist for new services (`docs/runbooks/RUNBOOK-007-observability-setup.md`).
4. **Automation:** Add CI/CD jobs leveraging `templates/platform-template/gitlab-ci/`.
5. **Documentation:** Every project requires an entry here plus runbook references.

