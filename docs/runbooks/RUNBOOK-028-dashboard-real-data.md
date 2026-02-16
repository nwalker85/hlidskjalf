# RUNBOOK-028: Dashboard Real Data Integration

## Overview

This runbook documents how the Hliðskjálf dashboard integrates with real-time data sources to provide live platform observability.

**Last Updated:** 2025-12-06  
**Status:** Active

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         Data Sources                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │port_registry │  │    Docker    │  │  PostgreSQL  │          │
│  │    .yaml     │  │     API      │  │   Database   │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                   │
│         │ (startup sync)   │ (discovery)      │ (queries)        │
│         ▼                  ▼                  ▼                   │
│  ┌──────────────────────────────────────────────────┐           │
│  │         Hliðskjálf Control Plane API             │           │
│  │              (FastAPI Backend)                    │           │
│  └──────────────────────┬───────────────────────────┘           │
│                          │                                        │
│                          │ REST API                               │
│                          ▼                                        │
│  ┌──────────────────────────────────────────────────┐           │
│  │         Hliðskjálf UI (Next.js)                  │           │
│  │     - React Query (data fetching)                 │           │
│  │     - OpenTelemetry (instrumentation)             │           │
│  └──────────────────────────────────────────────────┘           │
│                          │                                        │
│                          │ OTLP HTTP                              │
│                          ▼                                        │
│  ┌──────────────────────────────────────────────────┐           │
│  │          Grafana Stack                            │           │
│  │   Alloy → Prometheus/Loki/Tempo → Grafana        │           │
│  └──────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Backend APIs

### Platform Overview

**Endpoint:** `GET /api/v1/overview`

Returns platform-wide statistics:
- Total projects
- Total deployments
- Healthy/unhealthy deployment counts
- Ports allocated/available
- Deployment counts by environment (realm)
- Recent health checks

**Implementation:** `hlidskjalf/src/api/routes.py:51`

**Refresh Rate:** Frontend polls every 10 seconds

### Projects List

**Endpoint:** `GET /api/v1/projects?realm={realm}`

Returns all registered projects with optional realm filtering.

**Query Parameters:**
- `realm` (optional): Filter by environment (midgard, alfheim, asgard, etc.)

**Implementation:** `hlidskjalf/src/api/routes.py:167`

**Refresh Rate:** Frontend polls every 15 seconds

### Health Summary

**Endpoint:** `GET /api/v1/health/summary`

Returns aggregated health status:
- Health counts by status (healthy, degraded, unhealthy, unknown)
- Health status by realm
- Uptime percentage
- Recent failures

**Implementation:** `hlidskjalf/src/api/routes.py:399`

### Project Health

**Endpoint:** `GET /api/v1/projects/{project_id}/health`

Returns detailed health status for a specific project across all environments.

**Implementation:** `hlidskjalf/src/api/routes.py:442`

## Frontend Integration

### React Query Setup

The dashboard uses `@tanstack/react-query` for data fetching with automatic refetching:

```typescript
// Example: Fetch platform overview
const { data: stats, isLoading } = useQuery({
  queryKey: ['platform-overview'],
  queryFn: () => api.getOverview(),
  refetchInterval: 10000, // 10 seconds
});
```

**Configuration:** `hlidskjalf/ui/src/app/providers.tsx`

Default query options:
- `staleTime`: 5 seconds
- `refetchInterval`: 10 seconds

### API Client

**Location:** `hlidskjalf/ui/src/lib/api.ts`

The `HlidskjalfAPI` class provides typed methods for all backend endpoints:

```typescript
const api = new HlidskjalfAPI();

// Platform overview
await api.getOverview();

// Projects with realm filter
await api.listProjects('midgard');

// Health summary
await api.getHealthSummary();

// Project health
await api.getProjectHealth('my-project');
```

## Background Jobs

### Config Sync (Startup)

**Purpose:** Sync `port_registry.yaml` to database on application startup

**Implementation:** `hlidskjalf/src/services/config_loader.py:135`

**Trigger:** Application lifespan event in `main.py`

**What it does:**
1. Reads `config/port_registry.yaml`
2. Creates/updates `ProjectRecord` entries
3. Creates `PortAllocation` entries for each service
4. Logs summary of changes

### Docker Discovery (Background)

**Purpose:** Discover running Docker containers and update deployment records

**Implementation:** `hlidskjalf/src/services/deployment_manager.py:324`

**Interval:** Every 30 seconds

**What it does:**
1. Scans for containers with `ravenhelm.project` label
2. Updates `Deployment.container_ids`
3. Updates `Deployment.status` based on container state
4. Logs discovered containers

### Health Check Scheduler (Background)

**Purpose:** Periodically check health endpoints and update deployment status

**Implementation:** `hlidskjalf/src/services/deployment_manager.py:408`

**Interval:** Configurable (default: 60 seconds)

**What it does:**
1. Queries all deployments with health check URLs
2. Makes HTTP requests to health endpoints
3. Records response time and status
4. Creates `HealthCheckRecord` entries
5. Updates `Deployment.health_status`

## Database Schema

### Key Tables

**projects:**
- `id` (PK): Project identifier
- `name`: Display name
- `subdomain`: Nginx subdomain
- `project_type`: application, service, infrastructure

**deployments:**
- `id` (PK): Deployment identifier
- `project_id` (FK): Reference to project
- `environment`: Realm (midgard, alfheim, asgard, etc.)
- `status`: pending, deploying, running, stopped, failed
- `health_status`: healthy, degraded, unhealthy, unknown
- `container_ids`: JSON array of Docker container IDs
- `last_health_check`: Timestamp of last check

**port_allocations:**
- `id` (PK): Allocation identifier
- `project_id` (FK): Reference to project
- `port`: Allocated port number
- `port_type`: http, https, grpc, metrics, database
- `environment`: Realm
- `service_name`: Service identifier

**health_checks:**
- `id` (PK): Check identifier
- `deployment_id` (FK): Reference to deployment
- `status`: Health status result
- `response_time_ms`: Response time
- `metrics_snapshot`: JSON metrics data
- `checked_at`: Timestamp

## Performance Tuning

### Query Optimization

1. **Use Indexes:**
   - `projects.id` (PK)
   - `deployments.project_id` (FK)
   - `deployments.environment`
   - `health_checks.deployment_id` (FK)

2. **Limit Result Sets:**
   - Recent health checks: `LIMIT 10`
   - Health history: `LIMIT 100`

3. **Aggregate in Database:**
   - Use `func.count()` for statistics
   - Use `group_by()` for realm breakdowns

### Frontend Optimization

1. **React Query Caching:**
   - 5-second stale time prevents excessive refetching
   - Query invalidation on mutations

2. **Loading States:**
   - Skeleton loaders during initial fetch
   - Optimistic updates for mutations

3. **Error Handling:**
   - Graceful degradation on API failures
   - Retry logic with exponential backoff

## Troubleshooting

### Dashboard Shows No Data

**Symptoms:** Stats cards show 0, projects table is empty

**Diagnosis:**
1. Check if config sync ran on startup:
   ```bash
   docker logs gitlab-sre-hlidskjalf | grep "Configuration synced"
   ```

2. Check database:
   ```sql
   SELECT COUNT(*) FROM projects;
   SELECT COUNT(*) FROM deployments;
   ```

3. Check API health:
   ```bash
   curl https://hlidskjalf-api.ravenhelm.test/health
   ```

**Resolution:**
- Restart control plane to trigger config sync
- Verify `port_registry.yaml` exists and is valid
- Check database connection in logs

### Health Status Always "Unknown"

**Symptoms:** All deployments show health_status = "unknown"

**Diagnosis:**
1. Check if health check scheduler is running:
   ```bash
   docker logs gitlab-sre-hlidskjalf | grep "Health check scheduler"
   ```

2. Check if deployments have health_check_url set:
   ```sql
   SELECT id, health_check_url FROM deployments WHERE health_check_url IS NOT NULL;
   ```

**Resolution:**
- Ensure deployments have valid health check URLs
- Verify services are reachable from control plane container
- Check health check logs for errors

### Frontend Not Updating

**Symptoms:** Dashboard shows stale data despite backend changes

**Diagnosis:**
1. Check browser console for errors
2. Check React Query DevTools (if enabled)
3. Verify API responses in Network tab

**Resolution:**
- Clear browser cache
- Check if refetchInterval is working
- Verify API CORS configuration

### High Database Load

**Symptoms:** Slow API responses, high CPU on Postgres

**Diagnosis:**
1. Check query performance:
   ```sql
   SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;
   ```

2. Check active connections:
   ```sql
   SELECT COUNT(*) FROM pg_stat_activity;
   ```

**Resolution:**
- Add indexes on frequently queried columns
- Increase refetch intervals in frontend
- Implement connection pooling
- Add Redis caching layer

## Related Runbooks

- [RUNBOOK-007: Observability Stack Setup](RUNBOOK-007-observability-setup.md)
- [RUNBOOK-024: Add Shared Service](RUNBOOK-024-add-shared-service.md)
- [RUNBOOK-026: Let's Encrypt External HTTPS](RUNBOOK-026-letsencrypt-external-https.md)

## References

- FastAPI Documentation: https://fastapi.tiangolo.com/
- React Query Documentation: https://tanstack.com/query/latest
- OpenTelemetry JavaScript: https://opentelemetry.io/docs/instrumentation/js/
- SQLAlchemy Async: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

