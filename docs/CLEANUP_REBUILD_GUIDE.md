# Platform Cleanup & Rebuild Guide

This guide covers the `cleanup-rebuild-platform.sh` script for maintaining your Ravenhelm platform.

## Quick Reference

```bash
# Light cleanup (stop containers only, then restart)
./scripts/cleanup-rebuild-platform.sh --light --restart

# Medium cleanup (remove containers, keep data, rebuild)
./scripts/cleanup-rebuild-platform.sh --medium --rebuild --restart
```

**Note:** This script **never** removes volumes (databases, logs, etc.). Volume management requires explicit manual operations to prevent accidental data loss.

## Cleanup Levels

### 🟢 Light Cleanup (Default)
**What it does:**
- Stops all containers
- Removes orphaned containers
- **Keeps:** Everything (volumes, images, containers)

**When to use:**
- Quick restart needed
- Testing configuration changes
- No code changes

**Command:**
```bash
./scripts/cleanup-rebuild-platform.sh --light --restart
```

---

### 🟡 Medium Cleanup (Recommended)
**What it does:**
- Stops all containers
- Removes stopped containers
- Removes unused networks
- Removes dangling images
- **Keeps:** All volumes (databases, persistent data)

**When to use:**
- After code changes
- Rebuilding images
- Cleaning up orphaned resources
- **Most common use case**

**Command:**
```bash
./scripts/cleanup-rebuild-platform.sh --medium --rebuild --restart
```

**Safety:** This is safe to run regularly. Your data is never touched.

---

## Options Reference

| Option | Description |
|--------|-------------|
| `--light` | Stop containers only (default) |
| `--medium` | Stop and remove containers, keep all volumes (safe) |
| `--rebuild` | Rebuild images after cleanup |
| `--restart` | Restart platform after cleanup/rebuild |

## Common Scenarios

### Scenario 1: Code Changes (Frontend/Backend)
**You changed code and want to rebuild:**

```bash
# Stop, rebuild, restart
./scripts/cleanup-rebuild-platform.sh --medium --rebuild --restart
```

**Why medium?** Cleans up old containers/images but preserves database data.

---

### Scenario 2: Quick Restart
**No code changes, just need to restart:**

```bash
./scripts/cleanup-rebuild-platform.sh --light --restart
```

**Why light?** Fast, minimal cleanup, keeps everything.

---

### Scenario 3: Just Cleanup (Don't Restart)
**Debugging or manual control:**

```bash
# Stop and clean up, but don't restart
./scripts/cleanup-rebuild-platform.sh --medium

# Then manually start what you need
docker compose --env-file .env -f compose/docker-compose.infrastructure.yml up -d
```

---

### Scenario 4: Rebuild Only Hlidskjalf UI
**Frontend changes only:**

```bash
# Stop everything
./scripts/cleanup-rebuild-platform.sh --light

# Rebuild just the UI
docker compose --env-file .env up -d --build hlidskjalf-ui

# Restart
./scripts/start-platform.sh
```

---

## What Gets Cleaned

### Light Cleanup
- ✅ Stops containers
- ✅ Removes orphans
- ❌ Keeps containers
- ❌ Keeps images
- ❌ Keeps volumes
- ❌ Keeps networks

### Medium Cleanup
- ✅ Stops containers
- ✅ Removes stopped containers
- ✅ Removes unused networks
- ✅ Removes dangling images
- ❌ **Keeps ALL volumes** (databases, logs, etc.)
- ❌ Keeps used images

**Your data is always safe** - volumes are never automatically removed.

## Managing Volumes Manually

If you need to remove volumes (rare!), you must do so explicitly:

```bash
# List volumes
docker volume ls --filter "name=hlidskjalf"

# Remove a specific volume
docker volume rm hlidskjalf_<volume_name>

# ⚠️ DANGER: Remove all hlidskjalf volumes
docker volume ls --filter "name=hlidskjalf" -q | xargs -r docker volume rm
```

**Common volumes:**
- `hlidskjalf_postgres_data` - PostgreSQL databases
- `hlidskjalf_redis_data` - Redis cache/state
- `hlidskjalf_gitlab_data` - GitLab repositories/data
- `hlidskjalf_grafana_data` - Grafana dashboards
- `hlidskjalf_ollama_models` - Ollama LLM models (multi-GB!)

---

## Automated Use (CI/CD)

For automated cleanup and rebuild:

```bash
#!/bin/bash
# Automated cleanup and rebuild (safe - keeps data)
./scripts/cleanup-rebuild-platform.sh \
  --medium \
  --rebuild \
  --restart
```

This is safe for automation as volumes are never removed.

---

## Troubleshooting

### Script Fails to Stop Containers
**Symptom:** Containers are stuck or won't stop

**Solution:**
```bash
# Force stop all containers
docker ps -a -q | xargs -r docker stop -t 1
docker ps -a -q | xargs -r docker rm -f

# Then re-run cleanup
./scripts/cleanup-rebuild-platform.sh --medium
```

---

### "Volume is in use" Error
**Symptom:** Can't remove volume during deep cleanup

**Solution:**
```bash
# Ensure all containers are stopped
docker compose down -v --remove-orphans

# Force remove the volume
docker volume rm hlidskjalf_<volume_name> -f

# Or remove all hlidskjalf volumes
docker volume ls --filter "name=hlidskjalf" -q | xargs -r docker volume rm -f
```

---

### Rebuild Takes Forever
**Symptom:** Image rebuild is very slow

**Solution:**
```bash
# Clear builder cache first
docker builder prune -a -f

# Then rebuild
./scripts/cleanup-rebuild-platform.sh --medium --rebuild
```

---

### Out of Disk Space
**Symptom:** Docker runs out of space

**Solution:**
```bash
# Deep cleanup to free space
./scripts/cleanup-rebuild-platform.sh --deep

# Or manual cleanup
docker system prune -a --volumes -f  # REMOVES EVERYTHING
```

---

## Best Practices

### Daily Development
```bash
# Quick restart when needed
./scripts/cleanup-rebuild-platform.sh --light --restart
```

### After Git Pull (Code Changes)
```bash
# Medium cleanup with rebuild
./scripts/cleanup-rebuild-platform.sh --medium --rebuild --restart
```

### Weekly Maintenance
```bash
# Medium cleanup to remove cruft
./scripts/cleanup-rebuild-platform.sh --medium
docker system df  # Check disk usage
```

### Before Major Changes
```bash
# Clean up cruft
./scripts/cleanup-rebuild-platform.sh --medium --rebuild --restart

# Optionally backup volumes first
./scripts/backup-to-s3.sh  # If available
```

---

## Related Scripts

| Script | Purpose |
|--------|---------|
| `start-platform.sh` | Start all services in correct order |
| `create_traefik_networks.sh` | Create Docker networks |
| `backup-to-s3.sh` | Backup volumes to S3 |
| `init-platform.sh` | Initialize platform with bootstrap data |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Invalid arguments or user abort |
| `2` | Docker command failed |

---

## Questions?

- See `./scripts/cleanup-rebuild-platform.sh --help` for quick usage
- Check logs: `docker logs <container_name>`
- Platform docs: `docs/wiki/Operations.md`

