# MCP Server Design (Phase 4)

## 1. Goals & Scope

- **Primary focus for Phase 4:** ship an MCP server that exposes GitLab administration tools (projects, runners) _plus_ knowledge base management operations.  
- **Consumers:** Norns (via Bifrost MCP backend) and future automation agents.  
- **Success criteria:** authenticated MCP calls can (a) manage GitLab projects/groups/runners, (b) read/write knowledge base artifacts (GitLab wiki + repo docs), (c) emit auditable events.

### 1.1 Requirements Summary

| Domain | Required Capabilities (Phase 4) | Later Phases |
|--------|---------------------------------|--------------|
| GitLab Projects | Create project from template, set visibility, add webhooks, manage deploy tokens | Issue/MR automation, pipeline triggers |
| GitLab Runners | List runners, register (using service account), toggle maintenance, re-tag | Auto-scale runners via infrastructure MCP |
| Knowledge Base | Read wiki pages, list missing pages (based on docs/), create/update wiki page, sync docs to wiki | Runbook indexing, vector search, KB approvals |
| Security | Zitadel-issued OAuth token + SPIRE SVID optional, per-tool RBAC, audit log to Loki | OpenFGA policies, mTLS enforcement, per-agent rate limits |

## 2. Current State & Gaps

| Component | Status | Notes |
|-----------|--------|-------|
| Bifrost MCP backend (`bifrost-gateway/src/backends/mcp_backend.py`) | ✅ | Discovers `/tools`, `/resources`, streams SSE |
| MCP servers | ❌ | None deployed; docker-compose lacks MCP services |
| Auth | Partial | Zitadel SSO in platform, but MCP servers need OAuth 2.1 + forward auth +
| GitLab automation | Partial | CLI scripts + bootstrap-runbooks, not MCP-exposed |
| Knowledge base process (`docs/KNOWLEDGE_AND_PROCESS.md`) | ✅ defined | Needs automation to mirror docs → GitLab wiki |

## 3. Solution Overview

### 3.1 Technology Choices

| Layer | Choice | Rationale |
|-------|--------|-----------|
| MCP Server Framework | `modelcontextprotocol` Python package (official Anthropic SDK) running on FastAPI/Uvicorn | Native support for MCP schema, Python aligns with existing services, easy secrets integration |
| Containerization | Dedicated `mcp-server-gitlab` service in `docker-compose.yml` | Reuse existing Traefik ingress + SPIRE support |
| AuthN/Z | Zitadel OAuth 2.1 (client credentials) + Traefik forward auth + optional SPIRE SVID later | Matches edge zero-trust pattern |
| GitLab access | `python-gitlab` SDK + GitLab REST/GraphQL | Mature library, handles PAT/token auth, supports runners/projects/wiki |
| Knowledge Base sync | GitLab Wiki API + repo file operations (via GitLab API) | Aligns with doc strategy (MRs, wiki) |
| Secrets | LocalStack Secrets Manager (GitLab PAT, wiki token) | Already standardized |

### 3.2 High-Level Architecture

```
Norns (via Bifrost MCP backend)
        │  MCP/HTTP (JWT + optional SVID)
        ▼
┌───────────────────────────────┐
│ mcp-server-gitlab (FastAPI)   │
│   • Tool registry             │
│   • GitLab SDK client pool    │
│   • Knowledge Base sync       │
│   • Audit logger (Loki)       │
└──────────────┬────────────────┘
               │ REST/GraphQL
     ┌─────────┴─────────┐
     │ GitLab CE (local) │
     └───────────────────┘

Knowledge base assets (docs/, wiki) remain SoT inside GitLab repos.
```

## 4. Tool Design

### 4.1 GitLab Project / Runner Tools

| Tool Name | Arguments | Description |
|-----------|-----------|-------------|
| `gitlab.projects.create` | `name`, `group`, `visibility`, `template?` | Creates project from template; applies default labels/hooks |
| `gitlab.projects.add_webhook` | `project_id`, `url`, `events`, `token` | Configures webhook referencing Bifrost/Alert hooks |
| `gitlab.groups.add_member` | `group_id`, `user_email`, `role` | Adds user via service account |
| `gitlab.runners.list` | Optional filters (`group`, `status`) | Enumerate runners + tags |
| `gitlab.runners.register` | `name`, `tags`, `executor` | Creates runner registration token, returns config snippet |
| `gitlab.runners.maintenance` | `runner_id`, `state` | Toggle pause, update tags |

### 4.2 Knowledge Base Tools

| Tool Name | Arguments | Description |
|-----------|-----------|-------------|
| `knowledge.wiki.list_pages` | `section?`, `search?` | Lists wiki pages with metadata |
| `knowledge.wiki.read` | `slug` | Returns markdown content |
| `knowledge.wiki.upsert` | `slug`, `title`, `content_md`, `commit_message` | Creates/updates wiki page via GitLab API |
| `knowledge.docs.sync_status` | none | Compares `docs/` tree vs wiki (based on `KNOWLEDGE_AND_PROCESS` mapping) |
| `knowledge.docs.push` | `path`, `target_page`, `mode` | Creates MR to sync doc into wiki (optional auto-merge) |

## 5. Security & Compliance

1. **Authentication:**  
   - Traefik forward auth (oauth2-proxy) enforces Zitadel login for MCP endpoint.  
   - MCP server validates JWT audience & scope (`mcp.server.gitlab.manage`).  
   - Future: optional SPIRE SVID mutual TLS for agent pods.

2. **Authorization:**  
   - Tool-level ACL via config (e.g., only `hlidskjalf-agent` can call runner tools).  
   - Plan to integrate OpenFGA as per `POLICY_ALIGNMENT_AND_COMPLIANCE.md`.

3. **Secrets:**  
   - GitLab PAT + wiki tokens stored under `ravenhelm/dev/gitlab/mcp_service` in LocalStack Secrets Manager.  
   - MCP container fetches at startup via new secrets client module.

4. **Audit:**  
   - Every tool invocation logs structured event to Loki (labels: `mcp_tool`, `agent_id`, `target`).  
   - Optional GitLab comment/MR note to record wiki sync.

## 6. Deployment Plan

| Step | Description | Files |
|------|-------------|-------|
| 1 | Add `mcp-server-gitlab` service (FastAPI + modelcontextprotocol) | `docker-compose.yml`, new `services/mcp-server/` |
| 2 | Add Traefik route `mcp.gitlab.ravenhelm.test` with forward auth | `ravenhelm-proxy/dynamic.yml` |
| 3 | Implement server package (`services/mcp-server-gitlab/`) | `main.py`, `tools/gitlab_projects.py`, `tools/knowledge.py` |
| 4 | Wire secrets + configs | `.env`, LocalStack init |
| 5 | Tests | Pytest for tool functions (GitLab mocked) |
| 6 | Documentation | Runbook + update `PROJECT_PLAN.md` status |

### Phase Breakdown

1. **Phase 4A (This sprint):** MCP server skeleton, GitLab project/runner tools, read-only wiki tools.  
2. **Phase 4B:** Wiki upsert + doc sync automation, advanced RBAC, OpenFGA.  
3. **Phase 4C:** Additional servers (Zitadel, Docker), SPIRE/mTLS enforcement.

## 7. Open Questions

1. Knowledge base writes: should MCP apply changes directly or always open a GitLab MR?  
2. Runner registration workflow: integrate with secrets storage for tokens?  
3. Need for async job queue (RQ/Celery) for long-running wiki sync?

_Prepared for user review – feedback will drive implementation ordering._

