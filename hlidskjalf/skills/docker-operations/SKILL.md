---
name: docker-operations
description: Common Docker and Docker Compose operations for managing the Ravenhelm platform
version: 1.0.0
author: Norns
tags:
  - docker
  - containers
  - infrastructure
  - deployment
triggers:
  - docker
  - container
  - compose
  - start service
  - stop service
  - restart container
---

# Docker Operations

Essential Docker and Docker Compose commands for managing Ravenhelm services.

## Service Management

### Start Services
```bash
# Start all services
docker compose up -d

# Start specific services
docker compose up -d redis postgres langgraph

# Start with rebuild
docker compose up -d --build <service>
```

### Stop Services
```bash
# Stop all services
docker compose down

# Stop specific service
docker compose stop <service>

# Stop and remove volumes (DESTRUCTIVE)
docker compose down -v
```

### Restart Services
```bash
# Restart a service
docker compose restart <service>

# Restart with rebuild
docker compose up -d --build --force-recreate <service>
```

## Health Checking

```bash
# List running containers with health
docker compose ps

# Check specific container health
docker inspect --format='{{.State.Health.Status}}' <container>

# Watch container status
watch docker compose ps
```

## Logs and Debugging

```bash
# View logs
docker compose logs <service>

# Follow logs
docker compose logs -f <service>

# Last 100 lines
docker compose logs --tail 100 <service>
```

## Resource Management

```bash
# View resource usage
docker stats

# Prune unused resources
docker system prune -f

# Prune unused volumes (careful!)
docker volume prune -f
```

## Network Operations

```bash
# List networks
docker network ls

# Inspect network
docker network inspect <network>

# Create network
docker network create <network>
```

## Exec Into Containers

```bash
# Shell into container
docker exec -it <container> /bin/bash

# Run command in container
docker exec <container> <command>

# Run as root
docker exec -u root -it <container> /bin/bash
```

## Common Ravenhelm Services

| Service | Port | Description |
|---------|------|-------------|
| postgres | 5432 | Database |
| redis | 6379 | Cache |
| langgraph | 2024 | Agent API |
| hlidskjalf-ui | 3900 | Control plane UI |
| grafana | 3000 | Observability |
| prometheus | 9090 | Metrics |

## Troubleshooting

### Container won't start
1. Check logs: `docker compose logs <service>`
2. Check dependencies: `docker compose ps`
3. Verify ports: `lsof -i :<port>`
4. Check disk space: `df -h`

### Container keeps restarting
1. Check exit code: `docker inspect <container> --format='{{.State.ExitCode}}'`
2. Check health: `docker inspect <container> --format='{{.State.Health}}'`
3. Review restart policy in compose file

