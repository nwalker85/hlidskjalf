# Lessons Learned

This document captures operational insights, architectural decisions, and problem-solving patterns discovered during platform development.

---

## 1. Cross-Domain CORS and Mixed Content (2025-12-06)

### Problem
Dashboard failed to load on staging (`.dev`) domain with three critical errors:
1. **CORS Errors**: Frontend on `https://hlidskjalf.ravenhelm.dev` tried to call `https://hlidskjalf-api.ravenhelm.test` instead of `.dev`
2. **Mixed Content**: OpenTelemetry tried to send traces to `http://alloy.ravenhelm.test:4318` from HTTPS page - browsers block HTTP requests from HTTPS pages
3. **API 401 Unauthorized**: Even after fixing URLs, OPTIONS preflight requests were blocked by OAuth2-Proxy before CORS headers could be applied

### Solution
Multi-layered approach requiring frontend, backend, and edge proxy changes:

#### 1. Frontend API Client (`hlidskjalf/ui/src/lib/api.ts`)
Dynamic URL resolution based on current domain:
```typescript
const API_BASE = typeof window !== 'undefined' 
  ? window.location.origin.replace('hlidskjalf.', 'hlidskjalf-api.')
  : process.env.NEXT_PUBLIC_API_URL || "https://hlidskjalf-api.ravenhelm.test";
```

#### 2. Frontend Telemetry (`hlidskjalf/ui/src/lib/telemetry.ts`)
Route through Traefik using page's protocol:
```typescript
function getOTLPEndpoint(): string {
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_OTLP_ENDPOINT || 'https://otel.ravenhelm.test';
  }
  
  const hostname = window.location.hostname;
  const protocol = window.location.protocol; // 'http:' or 'https:'
  const domain = hostname.split('.').slice(-2).join('.');
  
  // Route through Traefik using otel subdomain (configured in dynamic.yml)
  return `${protocol}//otel.${domain}`;
}
```

#### 3. Edge Proxy (`ravenhelm-proxy/dynamic.yml`)
Added staging route for OTLP endpoint and ensured CORS middleware order:
```yaml
# New staging route for OTLP
otel-staging:
  rule: "Host(`otel.ravenhelm.dev`)"
  service: otel-svc
  middlewares:
    - secure-headers
  tls:
    certResolver: letsencrypt

# CORS-aware protected chain (CORS before auth)
protected-staging-cors:
  chain:
    middlewares:
      - cors-ravenhelm    # CORS headers first
      - secure-headers
      - zero-trust-auth-staging  # Auth last
```

#### 4. Backend (`hlidskjalf/src/main.py`)
CORS middleware already included all domains:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://hlidskjalf.ravenhelm.test",
        "https://hlidskjalf.ravenhelm.dev",  # ✓ Already present
        "https://hlidskjalf.ravenhelm.ai",
        ...
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Key Insights

#### Mixed Content Prevention
- **HTTPS pages cannot make HTTP requests** - browsers enforce strict mixed content policy
- Solution: Route all traffic through Traefik using the same protocol as the page
- Use `window.location.protocol` to dynamically match page security level
- **Centralize ingress**: Even observability endpoints should go through edge proxy

#### Dynamic URL Resolution
- Leverage `window.location.origin` for environment detection
- Single codebase works across `.test`, `.dev`, `.ai` without environment variables
- Fallback to env vars for server-side rendering contexts
- **Pattern**: `window.location.origin.replace('service-a.', 'service-b.')`

#### CORS Preflight Priority
- **ORDER MATTERS**: CORS middleware must run before authentication
- OPTIONS preflight requests need CORS headers to succeed
- If auth blocks preflight, browser never makes actual request
- **Correct chain**: `cors → secure-headers → auth`

#### Traefik as Universal Gateway
- Benefits of routing everything through Traefik:
  1. Single TLS termination point
  2. Consistent routing patterns
  3. Automatic Let's Encrypt certificates
  4. No need to expose internal ports
  5. Centralized middleware application
- Even non-HTTP services (OTLP, gRPC) benefit from Traefik routing

#### Container Rebuild vs Restart
- **Frontend code changes require rebuild**, not just restart
- JavaScript is bundled at **build time**, not runtime
- Symptom: Browser console shows old hardcoded URLs even after code changes
- Solution: `docker-compose up -d --build <service>` to rebuild image
- **Restart** (`docker-compose restart`) only restarts existing container with old image

### Implementation Details

**Deployment Steps**:
1. **Rebuild frontend**: `docker-compose up -d --build hlidskjalf-ui`
   - **Critical**: Code changes won't take effect until container is rebuilt
   - The JavaScript bundle is created at build time, not runtime
   - Simply restarting isn't enough - must rebuild to pick up code changes
2. Restart Traefik: `docker restart ravenhelm-traefik` (if dynamic.yml changed)

**Verification**:
```bash
# Test CORS headers
curl -s -H "Origin: https://hlidskjalf.ravenhelm.dev" \
  -X OPTIONS https://hlidskjalf-api.ravenhelm.dev/api/v1/overview -I \
  | grep -i "access-control"
# Expected: access-control-allow-origin: https://hlidskjalf.ravenhelm.dev

# Test OTLP endpoint
curl -s -o /dev/null -w "%{http_code}" https://otel.ravenhelm.dev/v1/traces
# Expected: 405 (Method Not Allowed - endpoint is accessible)
```

### Metrics
- **Before**: 100% API call failure rate on staging, console full of CORS and mixed content errors
- **After**: 0 CORS errors, 0 mixed content warnings, dashboard fully functional
- **Code changes**: 2 files modified, 1 Traefik route added
- **Environments**: Works seamlessly across `.test` (dev), `.dev` (staging), `.ai` (production)
- **Rebuild time**: ~40 seconds for frontend container

### Files Modified
1. `hlidskjalf/ui/src/lib/telemetry.ts` - Route through Traefik, use page protocol
2. `ravenhelm-proxy/dynamic.yml` - Added `otel-staging` route

### Files Verified (No Changes Needed)
1. `hlidskjalf/ui/src/lib/api.ts` - Already had dynamic resolution
2. `hlidskjalf/src/main.py` - CORS already configured correctly

### Related Issues
- Grafana SSO dual-environment fix (similar domain-based routing)
- OpenTelemetry frontend instrumentation setup
- Let's Encrypt HTTPS configuration
- Traefik CORS middleware chain ordering

---

## 2. Docker Compose Modularization (2025-12-04)

### Problem
Monolithic `docker-compose.yml` with 40 services caused:
- Cascading restarts when updating any service
- Slow development iteration (must start entire platform)
- Difficult to isolate issues
- Resource waste (running unnecessary services)

### Solution
Split into 8 modular compose stacks:
1. **Infrastructure** - postgres, redis, nats, localstack, openbao
2. **Security** - SPIRE, Zitadel, oauth2-proxy, spiffe-helpers
3. **Observability** - Grafana, Prometheus, Loki, Tempo, LangFuse, Phoenix
4. **Events** - Redpanda, Redpanda Console
5. **AI Infrastructure** - Ollama, HF models, Weaviate, embeddings, graphs
6. **LangGraph** - Norns agent, Hlidskjalf API & UI (isolated per user request)
7. **GitLab** - GitLab CE, GitLab Runner
8. **Integrations** - MCP server, n8n, LiveKit

### Key Insights
- **Isolation is stability**: LangGraph can restart without affecting infrastructure
- **Shared network works**: All stacks use `platform_net` - no network isolation needed yet
- **Convenience matters**: Quick-start scripts (`start-dev.sh`, `start-platform.sh`) improve UX
- **Backwards compatibility**: Wrapper file (`docker-compose-modular.yml`) preserves old behavior
- **Documentation critical**: RUNBOOK-030 ensures operators understand the new structure

### Implementation Details
- Used Docker Compose `include:` directive for shared definitions
- All volumes remain in `docker-compose.base.yml` for centralized management
- Scripts handle dependency order automatically
- Each stack validated with `docker compose config`

### Metrics
- **Dev startup time**: 40 services → 8 services (80% reduction)
- **Memory savings**: ~8GB in dev mode
- **Restart isolation**: Updating Grafana no longer restarts GitLab/LangGraph
- **Files created**: 8 compose files, 3 scripts, 1 runbook, 1 README

---

## 2. Database-Backed LLM Configuration (2025-12-06)

### Problem
LLM configuration was scattered across multiple mechanisms:
- Environment variables for Ollama, LM Studio, HuggingFace
- Session-based config in Huginn state (ephemeral)
- Hard-coded model selection in agent code
- No support for OpenAI/Anthropic API-based models
- Configuration UI in chat window (wrong context)
- No granular control per interaction type

This made it:
- Impossible to use cloud LLM providers
- Difficult to switch models without code changes
- Confusing for users (where do I configure this?)
- Wasteful (same model for reasoning and tool calling)

### Solution
Implemented centralized, database-backed LLM configuration system:

**Database Schema**:
- `llm_providers`: Provider configurations (OpenAI, Anthropic, custom)
- `llm_provider_models`: Available models per provider
- `llm_global_config`: Default config per interaction type
- `llm_user_config`: Optional per-user overrides

**Service Layer**:
- `LLMProviderService`: Manage providers, validate, fetch models
- `LLMConfigService`: Manage configs, factory for LangChain LLMs

**API Layer**:
- RESTful endpoints for providers and configuration
- Validation, model discovery, config updates

**UI Layer**:
- Dedicated "LLM Settings" panel on main dashboard
- Separate tabs for providers and model configuration
- Granular control per interaction type

**Integration**:
- Updated Norns supervisor to use `LLMConfigService`
- Updated specialized agents to use config service
- Updated planner to use config service
- Updated Muninn to use config service for embeddings

### Key Insights

**Architectural**:
- **Database as source of truth**: Configuration survives restarts, shareable across instances
- **Interaction types are key**: Different tasks need different models (reasoning vs tools)
- **Provider abstraction works**: OpenAI, Anthropic, custom servers all fit same interface
- **Validation is critical**: Must verify provider connectivity before use
- **Encryption matters**: API keys must be encrypted, not stored plaintext

**Operational**:
- **Seed defaults**: Provide sensible defaults so system works out-of-box
- **Graceful degradation**: Fall back to env vars if DB config fails
- **Model discovery**: Auto-fetch models from providers, don't hardcode lists
- **Temperature matters**: Different interaction types need different creativity levels
- **UI placement**: Configuration belongs on main dashboard, not in chat context

**Development**:
- **LangChain factory pattern**: Centralize LLM instantiation in config service
- **Async all the way**: Database, HTTP, and LLM calls must be async
- **Type safety**: Pydantic models + SQLAlchemy 2.0 provide excellent type hints
- **Migration first**: Schema changes before code changes
- **Test plan critical**: Comprehensive testing document ensures nothing is missed

### Implementation Details

**Interaction Types**:
1. **reasoning** (0.7): Main supervisor thinking - needs creativity
2. **tools** (0.1): Tool calling - needs determinism
3. **subagents** (0.5): Specialized tasks - balanced
4. **planning** (0.2): TODO generation - structured
5. **embeddings** (0.0): Vector search - no randomness

**Provider Types**:
1. **openai**: Official OpenAI API, auto-discovers models
2. **anthropic**: Claude models, hardcoded list (no discovery API)
3. **custom**: Any OpenAI-compatible server (vLLM, LM Studio, etc.)

**Security**:
- API keys encrypted via LocalStack Secrets Manager
- Secret paths stored in DB, not plaintext keys
- Encryption/decryption in `LLMProviderService`

**Files Created**:
- `hlidskjalf/migrations/versions/002_llm_providers_config.sql`
- `hlidskjalf/src/models/llm_config.py`
- `hlidskjalf/src/services/llm_providers.py`
- `hlidskjalf/src/services/llm_config.py`
- `hlidskjalf/src/api/llm_config.py` (refactored)
- `hlidskjalf/scripts/seed_llm_config.py`
- `hlidskjalf/ui/src/components/llm-config/LLMSettingsPanel.tsx`
- `hlidskjalf/ui/src/app/api/llm/providers/route.ts`
- `docs/LLM_CONFIGURATION_GUIDE.md`
- `docs/LLM_CONFIG_TESTING_PLAN.md`
- `docs/runbooks/RUNBOOK-026-llm-configuration-system.md`

**Files Updated**:
- `hlidskjalf/src/norns/agent.py` - Use config service
- `hlidskjalf/src/norns/specialized_agents.py` - Use config service
- `hlidskjalf/src/norns/planner.py` - Use config service
- `hlidskjalf/src/memory/muninn/store.py` - Use config service
- `hlidskjalf/ui/src/app/page.tsx` - Add LLM Settings button
- `docs/wiki/Runbook_Catalog.md` - Add RUNBOOK-026

**Files Archived**:
- `hlidskjalf/src/norns/llm_config_registry.py` - Old Kafka-based config
- `hlidskjalf/ui/src/components/llm-config/LLMConfigModal.tsx` - Old chat modal

### Metrics
- **Configuration flexibility**: 5 interaction types × N providers × M models
- **Supported providers**: 3 types (OpenAI, Anthropic, custom)
- **Default models**: 5 (gpt-4o, gpt-4o-mini, text-embedding-3-small)
- **API endpoints**: 10 new RESTful routes
- **UI components**: 1 main panel, 2 tabs, 5 interaction configs
- **Code removed**: ~200 lines of old local LLM logic
- **Code added**: ~1500 lines of new config system
- **Documentation**: 3 new docs, 1 runbook, 1 test plan

### Best Practices Established

1. **Always validate providers**: Don't assume API keys work
2. **Use low temp for tools**: Deterministic outputs for parsing
3. **Use high temp for reasoning**: Creative problem solving
4. **Separate embeddings**: Dedicated model for vector search
5. **Seed sensible defaults**: System should work immediately
6. **Document thoroughly**: Guide + runbook + test plan
7. **Test before deploying**: Comprehensive test plan prevents issues
8. **UI in right place**: Configuration on dashboard, not in chat

### Future Enhancements

Potential improvements for future phases:
1. **User-specific overrides**: Per-user model preferences
2. **Cost tracking**: Monitor spend per interaction type
3. **Model performance metrics**: Track latency, quality scores
4. **A/B testing**: Compare models for same task
5. **Auto-scaling**: Switch to cheaper models under load
6. **Model caching**: Reuse LLM instances across requests
7. **Streaming support**: Stream responses for better UX
8. **Fallback chains**: Try multiple providers if one fails

---

## Future Lessons

Add new sections here as operational patterns emerge.
