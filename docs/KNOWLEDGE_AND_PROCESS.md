# Knowledge & Process Strategy

This document captures how we structure the GitLab knowledge base, organize project work, and manage incidents across the Ravenhelm platform.

## 1. Wiki Content Strategy

### 1.1 Top-Level Sections

| Section | Purpose | Initial Source |
|---------|---------|----------------|
| **Overview** | Platform mission, guiding principles, current status | `EXECUTIVE_SUMMARY.md`, `PROJECT_PLAN.md` |
| **Architecture** | High-level diagrams, component overviews | `docs/architecture/*.md` |
| **Projects** | Dedicated subpages per application/initiative (goal, owners, links to repos & boards) | Populate as new projects start |
| **Operations** | Day-to-day runbooks, monitoring references, SRE checklists | `docs/runbooks/`, Grafana screenshots |
| **Administration** | Identity, access control, compliance policies | `LESSONS_LEARNED.md`, Zitadel/OpenBao configs |
| **Installation & Configuration** | Bootstrap steps for fresh environments | `RUNBOOK-001`, `RUNBOOK-006`, Terraform instructions |
| **Runbooks** | Linked index of all runbooks with tagging (`infra`, `security`, `voice`, etc.) | `docs/runbooks/*.md` |
| **Incident Library** | Post-incident reports, timeline captures, remediation tasks | Issues labeled `incident`, synced via automation |

### 1.2 Seeding Plan

1. **Overview & Architecture** – Link to the existing executive summary and architecture diagrams. Use embedded mermaid or PNG exports for quick reference.
2. **Projects** – Create a standard template ([Project Name], Description, Owners, GitLab repo, CI/CD pipelines, Runbooks). Seed with `platform-template` once pipelines stabilize.
3. **Operations** – Aggregate recurring operational tasks (backup checks, certificate rotation) and link back to runbooks.
4. **Administration** – Document Zitadel tenant structure, GitLab group policies, role matrix, and reference `RUNBOOK-009`.
5. **Installation & Configuration** – Step-by-step environment creation, referencing Terraform directories and Docker Compose overrides.
6. **Runbooks** – Auto-generate an index (script or manual) listing all `docs/runbooks/*.md` with short descriptions.
7. **Incident Library** – After each incident, capture summary + link to GitLab issue and postmortem.

### 1.3 Contribution Workflow

* **Create/Update via MR** – All wiki edits are authored in repo markdown (`docs/...`) and merged via GitLab MR to ensure review + history.
* **Templates** – Provide wiki page templates (`docs/wiki/templates/*.md`) for sections (Project, Incident, Service).
* **Ownership** – Assign a maintainer per section (e.g., Ops lead owns Operations pages). Document ownership table in Overview page.
* **Review Checklist** – Accuracy verified against source-of-truth (Terraform, runbooks). For diagrams, include both source (draw.io/mermaid) and rendered asset.

## 2. Project Board Strategy

### 2.1 Boards & Views

| Board | Columns | Filters / Swimlanes |
|-------|---------|---------------------|
| **Roadmap** | Backlog → Ready → In Progress → Review → Done | Filter `type::feature` |
| **Engineering** | Backlog → Design → Build → Review → Verify → Done → Blocked | Swimlane per priority (`priority::*`) |
| **Operations** | Intake → Triage → Implement → Validate → Closed → Blocked | Filter `type::infrastructure`, `type::maintenance`, `incident` |

Create these boards in the Ravenhelm group so they can display work across multiple repos.

### 2.2 Workflow Definition

* **Labels Drive Status** – Use `status::backlog`, `status::ready`, `status::in-progress`, `status::review`, `status::done`, `status::blocked`. Boards auto-group cards based on these labels.
* **WIP Limits** – Set explicit WIP counts per column (e.g., Engineering “Build” max 3). Violations highlighted via board configuration.
* **Triage Cadence** – Weekly backlog grooming; daily standup uses Engineering board “In Progress” view.
* **Templates & Checklists** – Issues must use the Bug/Feature/Incident templates shipping with the project, ensuring consistent data.

### 2.3 Automation Hooks

* **Scoped Labels** – Use scoped labels (`status::`, `type::`, `priority::`, `env::`) to prevent conflicting states.
* **Quick Actions** – Document `/label`, `/assign`, `/weight` commands in the project README and wiki.
* **Pipelines → Boards** – When CI pipelines fail on a merge request, automatically apply `status::blocked` via GitLab rule (future automation).
* **Incidents** – Issues labeled `incident` automatically appear on the Operations board with a dedicated swimlane.

## 3. Incident Tracking Process

### 3.1 Lifecycle

1. **Detection** – Alerts from Grafana/Alertmanager or manual reports create an Incident issue using the Incident template.
2. **Triage** – Assign Incident Commander (IC) and Scribe. Apply `priority::*`, `env::*`, and `status::in-progress`.
3. **Mitigation** – Record actions in the issue timeline, update Slack channel (e.g., `#incident-{date}`), and link relevant logs/dashboards.
4. **Resolution** – When service restored, move issue to `status::review`, capture resolution summary, and schedule postmortem.
5. **Postmortem** – Within 48h, complete post-incident analysis in the wiki’s Incident Library and link back to the issue; add follow-up tasks to the project board.

### 3.2 Communication & Ownership

| Role | Responsibilities |
|------|------------------|
| **Incident Commander** | Overall coordination, decision making, updates to stakeholders |
| **Scribe** | Real-time note taking, timeline capture, ensuring wiki/issue updated |
| **Subject Matter Experts** | Troubleshoot specific systems (Norns, Traefik, Terraform, etc.) |

**Channels:**
* Slack: `#oncall` for paging, `#incident-{date}` for live response.
* GitLab issue: Single source of truth (incident template auto-lists contacts, severity, impact).
* Wiki: Postmortem entry under “Incident Library”.

### 3.3 Metrics & Continuous Improvement

* **KPIs** – Track Mean Time To Acknowledge (MTTA) and Mean Time To Restore (MTTR) per incident via issue metadata (custom fields or labels).
* **Follow-ups** – Every incident must have at least one preventative action captured as a separate issue (linked) and scheduled on the project board.
* **Reviews** – Monthly Incident Review meeting to review trends, update runbooks, and reflect changes in the wiki.

### 3.4 Tooling Hooks

* GitLab issue template auto-tags incidents.
* Norns Observability agent streams incident summaries to the wiki/Slack (future automation).
* Alertmanager webhook → GitLab issue API for auto-creation (planned in Phase 6).

## 4. Documentation Intake Tracker

Every Markdown artifact (plus the external scaffold) now has an explicit landing zone in the wiki. Rows are ordered by topical priority so we can batch ingestion.

### 4.1 Program & Executive Docs

| Document | Purpose Snapshot | Wiki Placement | Next Action |
|----------|-----------------|----------------|-------------|
| `README.md` | High-level description of the Ravenhelm platform plus quickstart | **Overview → Platform Overview** | Extract concise “About Ravenhelm” blurb and link to service inventory. |
| `PROJECT_PLAN.md` | Phased roadmap, milestones, MCP tasks | **Overview → Roadmap** with cross-links to Projects section | Convert each phase into wiki roadmap cards; keep file as SoT. |
| `docs/EXECUTIVE_SUMMARY.md` | C-suite friendly summary of accomplishments | **Overview → Executive Summary** | Embed highlights verbatim; add chart placeholders. |
| `docs/FINAL_ACCOMPLISHMENTS.md` | Closure report for prior phases | **Overview → Milestones** | Create “Milestone Archive” wiki page; link PDF export. |
| `docs/DEPLOYMENT_SUMMARY.md` | Environment deployment punch list | **Installation & Configuration → Deployment Summary** | Translate into checklist with status badges. |
| `docs/NORNS_MISSION_LOG.md` | Timeline of Norns releases/events | **Projects → Norns → Mission Log** | Mirror entries into wiki and keep file as append-only log. |
| `docs/LESSONS_LEARNED.md` | Running log of lessons (e.g., GitLab SSO) | **Operations → Continuous Improvement** | Convert each numbered lesson into wiki cards tagged by domain. |
| `docs/README.md` | Index of repo docs | **Overview → Documentation Portal** | Embed as “How docs are organized” page. |
| `docs/KNOWLEDGE_AND_PROCESS.md` | Wiki/game-plan strategy (this file) | **Overview → Governance** | Link directly; treat as canonical policy. |
| `TODO.md` | Scratch backlog | **Projects → Backlog Intake** (as reference) | Cull done items into issues, then retire file once empty. |
| `/Users/nwalker/Documents/Enterprise_MultiPlatform_Architecture_Scaffold_v1.3.0.md` | Enterprise reference architecture (v1.3.0) | **Architecture → Enterprise Scaffold Reference** (mirrors Section 9-21) | Build wiki subpages per major section (Cost, Compliance, Change, DR) and cite original doc. |

### 4.2 Architecture & Compliance

| Document | Purpose Snapshot | Wiki Placement | Next Action |
|----------|-----------------|----------------|-------------|
| `docs/architecture/POLICY_ALIGNMENT_AND_COMPLIANCE.md` | Maps platform controls to regulations | **Administration → Compliance & Policy** | Break into per-framework child pages with evidence matrix. |
| `docs/architecture/SECURITY_HARDENING_PLAN.md` | Defense-in-depth hardening guidance | **Architecture → Security Architecture** | Summarize by layer (edge/service/data/tool). |
| `docs/architecture/TRAEFIK_MIGRATION_PLAN.md` | Nginx → Traefik plan with autodiscovery | **Installation & Configuration → Network & Proxy** | Convert into runbook-style wiki page and link to Traefik runbook. |
| `docs/architecture/REORGANIZATION.md` | Notes on doc move and folder structure | **Overview → Documentation Portal** | Reference as historical appendix once wiki structure is live. |

### 4.3 Runbooks & Operations

All runbooks live under **Runbooks** but we’ll also add secondary tags (infra, security, voice, identity, observability).

| Document | Purpose Snapshot | Wiki Placement | Next Action |
|----------|-----------------|----------------|-------------|
| `docs/runbooks/RUNBOOK-001-deploy-docker-service.md` | Standard docker deploy checklist | Runbooks → Infrastructure | Convert to wiki runbook template. |
| `docs/runbooks/RUNBOOK-002-add-traefik-domain.md` | Adding new Traefik routes | Runbooks → Networking | Embed label matrix (entrypoint, router, middleware). |
| `docs/runbooks/RUNBOOK-003-generate-certificates.md` | mkcert / certificate process | Runbooks → Security | Include troubleshooting block for macOS keychain. |
| `docs/runbooks/RUNBOOK-004-spire-management.md` | SPIRE lifecycle | Runbooks → Security | Add mTLS verification screenshots. |
| `docs/runbooks/RUNBOOK-005-file-ownership-permissions.md` | Ownership corrections (UID/GID 1001) | Runbooks → Operations | Reference lesson learned #1. |
| `docs/runbooks/RUNBOOK-006-zitadel-sso.md` | Zitadel SSO procedure | Runbooks → Identity | Tie to Grafana/GitLab SSO sections. |
| `docs/runbooks/RUNBOOK-007-observability-setup.md` | OTEL → Grafana Alloy pipeline | Runbooks → Observability | Provide Grafana dashboard IDs. |
| `docs/runbooks/RUNBOOK-009-gitlab-sso.md` | GitLab OIDC integration | Runbooks → Identity | Already synced; link to Lessons Learned entries 12–14. |
| `docs/runbooks/RUNBOOK-010-deploy-agent.md` | Agent deployment template | Runbooks → Agents | Reference skill loader + MCP registration. |
| `docs/runbooks/RUNBOOK-010-secret-rotation.md` | Secret rotation workflow | Runbooks → Security | Clarify differences for Zitadel/OpenBao. |
| `docs/runbooks/RUNBOOK-020-add-bifrost-adapter.md` | Bifrost adapter install | Runbooks → Voice / Realtime | Pair with `bifrost-gateway` README. |
| `docs/runbooks/RUNBOOK-021-add-bifrost-ai-backend.md` | Wiring AI backend into Bifrost | Runbooks → Voice / Realtime | Include port registry prereqs. |
| `docs/runbooks/RUNBOOK-022-configure-voice-agent.md` | Voice agent setup | Runbooks → Voice / Realtime | Add diagrams from Executive Voice Console spec. |
| `docs/runbooks/ravenhelm-traefik-autodiscovery.md` | Traefik autodiscovery process | Runbooks → Networking | Cross-link to Traefik migration architecture doc. |
| `docs/runbooks/voice-webrtc.md` | Voice/WebRTC deployment | Runbooks → Voice / Realtime | Integrate LiveKit mTLS notes. |

### 4.4 Reference, Skills, and Component READMEs

| Document | Purpose Snapshot | Wiki Placement | Next Action |
|----------|-----------------|----------------|-------------|
| `docs/reference/HOW_TO_CREATE_AGENT_SWARM.md` | Agent swarm assembly guide | **Projects → Norns → Agent Foundry** | Summarize steps + link to skills catalog. |
| `docs/reference/NORNS_DEEP_AGENT_SYSTEM.md` | Deep agent system prompt + behavior | **Projects → Norns → Architecture** | Ensure version control + change log. |
| `docs/reference/README_AGENT_SWARM.md` | Swarm README for external sharing | **Projects → Norns → Overview** | Embed as “Shareable summary”. |
| `docs/reference/TEST_DEEP_AGENT.md` | Test plan for deep agent | **Projects → QA & Validation** | Convert into structured test cases in wiki. |
| `hlidskjalf/skills/*.md` | Skill definitions (create-skill, subagent type, etc.) | **Operations → Skills Catalog** | Auto-generate wiki table linking to each `SKILL.md`. |
| `hlidskjalf/src/norns/.changelog/20251202_231815_tools.md` | Tooling release notes | **Projects → Norns → Release Notes** | Aggregate multiple changelog files when they appear. |
| `hlidskjalf/src/memory/README.md` | Memory subsystem overview | **Architecture → Raven Model (Huginn/Frigg/Muninn/Mímir/Hel)** | Add diagrams showing data planes. |
| `hlidskjalf/README.md` | Service-specific README | **Projects → Core Platform → hlidskjalf** | Keep as technical quickstart; link from wiki. |
| `bifrost-gateway/README.md` | Voice gateway instructions | **Projects → Voice Stack → Bifrost** | Pair with runbooks 020–022. |
| `libs/ravenvoice/README.md` | Library usage for voice components | **Projects → Voice Stack → Libraries** | Provide usage snippets + version info. |
| `ravenhelm-proxy/README.md` | Reverse proxy configuration details | **Installation & Configuration → Networking** | Map to Traefik/Traefik runbooks. |
| `templates/platform-template/README.md` | GitLab template usage | **Projects → GitLab Templates** | Document how to bootstrap new product repos. |
| `templates/platform-template/.gitlab/issue_templates/*.md` | Issue templates (Bug/Feature/Incident) | **Projects → GitLab Templates → Issue Templates** | Embed screenshots and describe usage workflow. |
| `templates/platform-template/.gitlab/merge_request_templates/Default.md` | MR template | **Projects → GitLab Templates → Merge Process** | Highlight required checklist fields. |

### 4.5 Gap Summary & Next Steps

1. **Architecture vs. Wiki** – All four architecture docs plus the external scaffold feed the Architecture, Administration, and Installation sections. Action: create a wiki “Architecture Index” page that links each subtopic (Security, Compliance, Traefik migration, Enterprise Scaffold).  
2. **Runbooks Indexing** – Every runbook now has an assigned tag; next step is to auto-generate the Runbooks landing page with tag filters and link each runbook.  
3. **Skills & Component Docs** – Skills, component READMEs, and changelog entries will surface under Projects/Operations to keep Norns knowledge centralized. Implement a nightly job (or GitLab pipeline) that syncs the skills directory into the wiki table.  
4. **Enterprise Scaffold Integration** – Section owners (Architecture, Compliance, Incident Response, Change Management) must lift the v1.3.0 content into dedicated wiki pages, citing the `/Users/nwalker/Documents/Enterprise_MultiPlatform_Architecture_Scaffold_v1.3.0.md` file as source of truth and noting any deltas from local implementation.

## 5. Architecture Index Draft (Generated by Norns)

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

### Migration TODOs

1. **Complete SPIRE workload registration** – Execute `./spire/init-spire.sh bootstrap` and register remaining services in `docker-compose.yml` with SPIFFE IDs referenced in `PROJECT_PLAN.md` Phase 0 checklist.
2. **Migrate from nginx to Traefik** – Implement autodiscovery routing using `docs/architecture/TRAEFIK_MIGRATION_PLAN.md` and update all service labels/entrypoints.
3. **Deploy production-ready Zitadel** – Run `scripts/bootstrap-zitadel.sh` and configure SSO for every service listed in `PROJECT_PLAN.md` Phase 1.
4. **Implement secrets rotation** – Move plaintext credentials from `.env` to LocalStack Secrets Manager using `scripts/rotate-secrets.sh` plus `docs/runbooks/RUNBOOK-010-secret-rotation.md`.
5. **Standardize file ownership** – Apply the `ravenhelm:1001:1001` model via `scripts/init-platform.sh` and confirm mounts per `docs/runbooks/RUNBOOK-005-file-ownership-permissions.md`.
6. **Establish MCP security** – Protect all MCP servers with OAuth 2.1 as outlined in Phase 4 of `PROJECT_PLAN.md`.

## 6. Runbook Catalog (Generated by Norns)

| Runbook | Focus Area Tags | Primary Tasks | Prerequisites |
|---------|----------------|---------------|--------------|
| [RUNBOOK-001-deploy-docker-service.md](docs/runbooks/RUNBOOK-001-deploy-docker-service.md) | `infra`, `docker`, `deployment` | Deploy new Docker services, manage port registry, wire Traefik routes | Docker/Docker Compose, port registry access, Traefik labels |
| [RUNBOOK-002-add-traefik-domain.md](docs/runbooks/RUNBOOK-002-add-traefik-domain.md) | `infra`, `networking`, `traefik` | Add new domains, configure autodiscovery labels, update DNS | Completed RUNBOOK-001, dnsmasq for `*.ravenhelm.test` |
| [RUNBOOK-003-generate-certificates.md](docs/runbooks/RUNBOOK-003-generate-certificates.md) | `infra`, `security`, `certificates` | Generate/rotate mkcert certs, manage domain inventory | mkcert installed and CA trusted, domain list |
| [RUNBOOK-004-spire-management.md](docs/runbooks/RUNBOOK-004-spire-management.md) | `security`, `spire`, `mtls` | Bootstrap SPIRE, issue workload identities, troubleshoot mTLS | Docker/Docker Compose, OpenSSL, intra-network reachability |
| [RUNBOOK-005-file-ownership-permissions.md](docs/runbooks/RUNBOOK-005-file-ownership-permissions.md) | `infra`, `permissions` | Enforce ravenhelm UID/GID 1001 across volumes | Platform init scripts, filesystem access |
| [RUNBOOK-006-zitadel-sso.md](docs/runbooks/RUNBOOK-006-zitadel-sso.md) | `identity`, `sso`, `oauth` | Configure Zitadel SSO, manage roles, federate services | Zitadel deployed, OAuth credentials, service endpoints |
| [RUNBOOK-007-observability-setup.md](docs/runbooks/RUNBOOK-007-observability-setup.md) | `observability`, `monitoring` | Deploy Grafana stack, configure Alloy collector, load dashboards | Docker stack running, Traefik routing |
| [RUNBOOK-009-gitlab-sso.md](docs/runbooks/RUNBOOK-009-gitlab-sso.md) | `identity`, `gitlab` | Wire GitLab CE to Zitadel, trust mkcert CA, sync admin roles | Zitadel + GitLab up, CA certificate mounted |
| [RUNBOOK-010-deploy-agent.md](docs/runbooks/RUNBOOK-010-deploy-agent.md) | `agents`, `deployment` | Register new agents, connect to Kafka/NATS, publish skills | Port/agent registries, Kafka topics, skills definitions |
| [RUNBOOK-010-secret-rotation.md](docs/runbooks/RUNBOOK-010-secret-rotation.md) | `security`, `secrets` | Rotate secrets in AWS/LocalStack, refresh services | AWS/LocalStack access, service restart capability |
| [RUNBOOK-020-add-bifrost-adapter.md](docs/runbooks/RUNBOOK-020-add-bifrost-adapter.md) | `voice`, `bifrost` | Build/install new messaging adapters | Python 3.11+, target platform API creds |
| [RUNBOOK-021-add-bifrost-ai-backend.md](docs/runbooks/RUNBOOK-021-add-bifrost-ai-backend.md) | `voice`, `ai` | Integrate AI backends for Bifrost | AI service endpoints, API keys |
| [RUNBOOK-022-configure-voice-agent.md](docs/runbooks/RUNBOOK-022-configure-voice-agent.md) | `voice`, `livekit`, `realtime` | Configure voice agents, LiveKit, speech services | LiveKit server, Deepgram/ElevenLabs APIs |
| [ravenhelm-traefik-autodiscovery.md](docs/runbooks/ravenhelm-traefik-autodiscovery.md) | `infra`, `networking` | Enable Traefik autodiscovery, wildcard DNS, host tooling | Docker Desktop, Homebrew, mkcert |
| [voice-webrtc.md](docs/runbooks/voice-webrtc.md) | `voice`, `webrtc`, `twilio` | Twilio WebRTC integration, PSTN bridging | Twilio Voice SDK + credentials, UI access |

### Follow-ups

- **Standardize runbook metadata** – add consistent YAML frontmatter to every `docs/runbooks/RUNBOOK-*.md` (category, priority, owner, last_updated).
- **Map runbook dependencies** – document upstream/downstream relationships (e.g., RUNBOOK-002 depends on RUNBOOK-001) in the wiki for quick navigation.
- **Automate common procedures** – script repetitive steps from `RUNBOOK-003` and `RUNBOOK-005` to reduce manual toil.
- **Cross-link the voice stack** – integrate RUNBOOK-020/021/022 plus `voice-webrtc.md` into a single workflow page covering the full voice pipeline.
- **Automated catalog build** – create a GitLab pipeline to regenerate this table whenever runbooks change, matching the plan in `docs/KNOWLEDGE_AND_PROCESS.md`.
- **Quarterly validation** – schedule a recurring review to dry-run each runbook against a clean environment and capture deltas/lessons.

