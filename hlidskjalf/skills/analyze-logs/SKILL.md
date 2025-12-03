---
name: analyze-logs
description: Analyze logs and error messages to diagnose issues in the Ravenhelm platform
version: 1.0.0
author: Norns
tags:
  - debugging
  - observability
  - troubleshooting
triggers:
  - analyze logs
  - debug error
  - troubleshoot
  - what went wrong
  - investigate issue
---

# Analyze Logs

Systematic approach to analyzing logs and diagnosing issues in the Ravenhelm platform.

## Quick Diagnosis Steps

1. **Identify the timeframe**: When did the issue start?
2. **Locate relevant logs**: Which service/container is affected?
3. **Filter for errors**: Look for ERROR, WARN, Exception patterns
4. **Trace the flow**: Follow request IDs or correlation IDs
5. **Check dependencies**: Are upstream/downstream services healthy?

## Common Log Locations

| Service | Log Location |
|---------|-------------|
| Docker containers | `docker logs <container>` |
| LangGraph | Terminal running `langgraph dev` |
| Next.js UI | Terminal running `npm run dev` |
| Nginx | `/var/log/nginx/` or container logs |
| PostgreSQL | Container logs or `/var/log/postgresql/` |

## Useful Commands

```bash
# Get recent logs from a container
docker logs --tail 100 <container_name>

# Follow logs in real-time
docker logs -f <container_name>

# Search for errors
docker logs <container_name> 2>&1 | grep -i error

# Get logs since a time
docker logs --since="2024-01-01T00:00:00" <container_name>

# All container logs with compose
docker compose logs --tail 50
```

## Error Pattern Analysis

### Connection Errors
- `ECONNREFUSED`: Service not running or wrong port
- `ETIMEDOUT`: Network issue or service overloaded
- `Connection reset`: Service crashed or firewall

### Authentication Errors
- `401 Unauthorized`: Invalid or expired credentials
- `403 Forbidden`: Missing permissions
- `Invalid API key`: Check environment variables

### Database Errors
- `relation does not exist`: Missing table/migration
- `connection refused`: Database not running
- `too many connections`: Connection pool exhausted

## Recommended Actions

After identifying the issue:
1. Document the root cause
2. Apply the fix
3. Verify the fix works
4. Consider creating a skill for this specific issue type

