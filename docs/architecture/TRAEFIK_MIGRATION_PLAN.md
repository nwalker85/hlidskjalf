# Ravenhelm Platform - Traefik Migration Plan

## 🎯 Why This Solves Our Problems

The port conflicts we encountered (SAAA using ports 80/443/5678) are eliminated by:
- **Single edge proxy** (Traefik) handles all `*.ravenhelm.test` routing
- **Automatic service discovery** via Docker labels (no manual nginx configs)
- **Network isolation** per stack for security and organization
- **Zero port exposure** on host (services only exposed through Traefik)

## 📋 Current State vs Traefik Architecture

### Current Architecture (Conflicting)
```
Host Ports 80/443 ← SAAA nginx (blocking ravenhelm-proxy)
Host Ports 80/443 ← ravenhelm-proxy (wanted, can't bind)
Host Various    ← Individual service ports (GitLab 11443, etc.)
```

### New Traefik Architecture
```
Host Port 443 ← Traefik (single edge proxy)
    ↓
    ├── gitlab.ravenhelm.test → gitlab_net (10.20.0.0/24) → GitLab
    ├── saaa.ravenhelm.test → saaa_net (10.30.0.0/24) → SAAA
    ├── grafana.observe.ravenhelm.test → platform_net (10.10.0.0/24) → Grafana
    ├── hlidskjalf.ravenhelm.test → platform_net → Hlidskjalf
    └── *.ravenhelm.test → Auto-discovered via Docker labels
```

## 🏗️ Network Architecture

### Proposed Networks

```yaml
networks:
  edge:
    subnet: 10.0.10.0/24    # Traefik edge network
  
  platform_net:
    subnet: 10.10.0.0/24    # Ravenhelm platform services
                            # (Hlidskjalf, Grafana, Prometheus, Redis, etc.)
  
  gitlab_net:
    subnet: 10.20.0.0/24    # GitLab + Runner
  
  saaa_net:
    subnet: 10.30.0.0/24    # SAAA/AgentSwarm/AgentCrucible
  
  m2c_net:
    subnet: 10.40.0.0/24    # M2C Demo
  
  tinycrm_net:
    subnet: 10.50.0.0/24    # TinyCRM Demo
```

## 🚀 Migration Steps

### Phase 1: Setup Traefik Edge (Foundation)

**1.1 Create Network Structure**
```bash
cd /Users/nwalker/Development/hlidskjalf

# Create all networks
docker network create --driver bridge --subnet 10.0.10.0/24 edge
docker network create --driver bridge --subnet 10.10.0.0/24 platform_net
docker network create --driver bridge --subnet 10.20.0.0/24 gitlab_net
docker network create --driver bridge --subnet 10.30.0.0/24 saaa_net
docker network create --driver bridge --subnet 10.40.0.0/24 m2c_net
docker network create --driver bridge --subnet 10.50.0.0/24 tinycrm_net
```

**1.2 Deploy Traefik Edge Proxy**

Create `/Users/nwalker/Development/hlidskjalf/traefik-edge/docker-compose.yml`:

```yaml
version: "3.9"

services:
  traefik:
    image: traefik:v3.1
    container_name: ravenhelm-traefik
    restart: unless-stopped
    command:
      # Docker provider
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--providers.docker.network=edge"
      
      # Entry points
      - "--entrypoints.websecure.address=:443"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.web.http.redirections.entryPoint.to=websecure"
      - "--entrypoints.web.http.redirections.entryPoint.scheme=https"
      
      # Dashboard (dev only)
      - "--api.dashboard=true"
      - "--api.insecure=true"
      
      # Logging
      - "--log.level=INFO"
      - "--accesslog=true"
      
      # Allow self-signed backend certs
      - "--serversTransport.insecureSkipVerify=true"
      
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"  # Dashboard at traefik.ravenhelm.test:8080
      
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "./certs:/certs:ro"
      
    networks:
      - edge
      - platform_net
      - gitlab_net
      - saaa_net
      - m2c_net
      - tinycrm_net
    
    labels:
      # Traefik dashboard
      - "traefik.enable=true"
      - "traefik.http.routers.dashboard.rule=Host(`traefik.ravenhelm.test`)"
      - "traefik.http.routers.dashboard.entrypoints=websecure"
      - "traefik.http.routers.dashboard.tls=true"
      - "traefik.http.routers.dashboard.service=api@internal"

networks:
  edge:
    external: true
  platform_net:
    external: true
  gitlab_net:
    external: true
  saaa_net:
    external: true
  m2c_net:
    external: true
  tinycrm_net:
    external: true
```

**1.3 Copy Certificates**
```bash
mkdir -p /Users/nwalker/Development/hlidskjalf/traefik-edge/certs
cp /Users/nwalker/Development/hlidskjalf/ravenhelm-proxy/config/certs/server.* \
   /Users/nwalker/Development/hlidskjalf/traefik-edge/certs/
```

### Phase 2: Migrate SAAA Stack

**2.1 Stop Current SAAA nginx**
```bash
cd /path/to/saaa
docker compose stop nginx
```

**2.2 Update SAAA docker-compose.yml**

Add Traefik labels to frontend service:
```yaml
services:
  frontend:
    # ... existing config ...
    networks:
      - saaa_net
      - default  # Keep internal network for service communication
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=saaa_net"
      
      # Main SAAA frontend
      - "traefik.http.routers.saaa.rule=Host(`saaa.ravenhelm.test`) || Host(`agentcrucible.ravenhelm.test`)"
      - "traefik.http.routers.saaa.entrypoints=websecure"
      - "traefik.http.routers.saaa.tls=true"
      - "traefik.http.services.saaa.loadbalancer.server.port=3000"

networks:
  saaa_net:
    external: true
  default:
    name: saaa_internal
```

Add labels to backend/agents as needed for direct API access.

### Phase 3: Migrate Ravenhelm Platform Services

**3.1 Update docker-compose.yml for Platform**

Add Traefik labels to key services:

```yaml
services:
  # Observability Stack
  grafana:
    # ... existing config ...
    networks:
      - platform_net
      - gitlab-network  # Keep for inter-service communication
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=platform_net"
      - "traefik.http.routers.grafana.rule=Host(`grafana.observe.ravenhelm.test`) || Host(`observe.ravenhelm.test`)"
      - "traefik.http.routers.grafana.entrypoints=websecure"
      - "traefik.http.routers.grafana.tls=true"
      - "traefik.http.services.grafana.loadbalancer.server.port=3000"
  
  langfuse:
    networks:
      - platform_net
      - gitlab-network
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=platform_net"
      - "traefik.http.routers.langfuse.rule=Host(`langfuse.observe.ravenhelm.test`)"
      - "traefik.http.routers.langfuse.entrypoints=websecure"
      - "traefik.http.routers.langfuse.tls=true"
      - "traefik.http.services.langfuse.loadbalancer.server.port=3000"
  
  phoenix:
    networks:
      - platform_net
      - gitlab-network
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=platform_net"
      - "traefik.http.routers.phoenix.rule=Host(`phoenix.observe.ravenhelm.test`)"
      - "traefik.http.routers.phoenix.entrypoints=websecure"
      - "traefik.http.routers.phoenix.tls=true"
      - "traefik.http.services.phoenix.loadbalancer.server.port=6006"
  
  redpanda-console:
    networks:
      - platform_net
      - gitlab-network
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=platform_net"
      - "traefik.http.routers.redpanda.rule=Host(`events.ravenhelm.test`) || Host(`redpanda.ravenhelm.test`)"
      - "traefik.http.routers.redpanda.entrypoints=websecure"
      - "traefik.http.routers.redpanda.tls=true"
      - "traefik.http.services.redpanda.loadbalancer.server.port=8080"
  
  openbao:
    networks:
      - platform_net
      - gitlab-network
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=platform_net"
      - "traefik.http.routers.vault.rule=Host(`vault.ravenhelm.test`)"
      - "traefik.http.routers.vault.entrypoints=websecure"
      - "traefik.http.routers.vault.tls=true"
      - "traefik.http.services.vault.loadbalancer.server.port=8200"
  
  n8n:
    networks:
      - platform_net
      - gitlab-network
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=platform_net"
      - "traefik.http.routers.n8n.rule=Host(`n8n.ravenhelm.test`)"
      - "traefik.http.routers.n8n.entrypoints=websecure"
      - "traefik.http.routers.n8n.tls=true"
      - "traefik.http.services.n8n.loadbalancer.server.port=5678"
  
  hlidskjalf:
    networks:
      - platform_net
      - gitlab-network
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=platform_net"
      - "traefik.http.routers.hlidskjalf-api.rule=Host(`hlidskjalf-api.ravenhelm.test`)"
      - "traefik.http.routers.hlidskjalf-api.entrypoints=websecure"
      - "traefik.http.routers.hlidskjalf-api.tls=true"
      - "traefik.http.services.hlidskjalf-api.loadbalancer.server.port=8900"
  
  hlidskjalf-ui:
    networks:
      - platform_net
      - gitlab-network
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=platform_net"
      - "traefik.http.routers.hlidskjalf.rule=Host(`hlidskjalf.ravenhelm.test`)"
      - "traefik.http.routers.hlidskjalf.entrypoints=websecure"
      - "traefik.http.routers.hlidskjalf.tls=true"
      - "traefik.http.services.hlidskjalf.loadbalancer.server.port=3900"
  
  # Add more services...

networks:
  platform_net:
    external: true
  gitlab-network:
    driver: bridge
    ipam:
      config:
        - subnet: 10.88.0.0/16
```

**3.2 Remove nginx proxy containers**

Since Traefik handles routing, remove:
- `nginx` (GitLab SSL proxy)
- `observe-nginx` (Observability SSL proxy)
- `events-nginx` (Redpanda Console SSL proxy)
- `vault-nginx` (OpenBao SSL proxy)

These are no longer needed - Traefik handles all SSL termination.

**3.3 Remove exposed ports**

Update docker-compose.yml to remove host port mappings:
```yaml
# Before:
ports:
  - "3000:3000"  # Remove this

# After:
# No ports section - Traefik handles routing
```

### Phase 4: Migrate GitLab

```yaml
services:
  gitlab:
    # ... existing config ...
    networks:
      - gitlab_net
      - gitlab-network
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=gitlab_net"
      - "traefik.http.routers.gitlab.rule=Host(`gitlab.ravenhelm.test`)"
      - "traefik.http.routers.gitlab.entrypoints=websecure"
      - "traefik.http.routers.gitlab.tls=true"
      - "traefik.http.services.gitlab.loadbalancer.server.port=80"
      
      # GitLab Registry
      - "traefik.http.routers.registry.rule=Host(`registry.gitlab.ravenhelm.test`)"
      - "traefik.http.routers.registry.entrypoints=websecure"
      - "traefik.http.routers.registry.tls=true"
      - "traefik.http.services.registry.loadbalancer.server.port=5050"

networks:
  gitlab_net:
    external: true
  gitlab-network:
    driver: bridge
```

### Phase 5: Deployment Order

```bash
# 1. Stop conflicting services
cd /path/to/saaa && docker compose stop nginx
cd /path/to/m2c-demo && docker compose stop n8n

# 2. Create networks
cd /Users/nwalker/Development/hlidskjalf
./scripts/create_traefik_networks.sh

# 3. Start Traefik edge
cd traefik-edge
docker compose up -d

# 4. Migrate platform services
cd /Users/nwalker/Development/hlidskjalf
docker compose down  # Stop old services
# Update docker-compose.yml with Traefik labels
docker compose up -d

# 5. Migrate SAAA
cd /path/to/saaa
# Update docker-compose.yml with Traefik labels
docker compose up -d

# 6. Test all endpoints
curl -k https://grafana.observe.ravenhelm.test
curl -k https://saaa.ravenhelm.test
curl -k https://gitlab.ravenhelm.test
```

## 📊 Benefits of This Architecture

### For the Norns Multi-Agent System

1. **Zero-Configuration Service Discovery**
   - New agents just add Docker labels
   - No manual nginx config editing
   - Automatic routing based on hostname rules

2. **Network Isolation**
   - Each agent squad can have its own network
   - Better security boundaries
   - Cleaner service organization

3. **Scalability**
   - Easy to add new services/agents
   - Load balancing built-in
   - Health checking via Traefik

4. **Observability**
   - Traefik dashboard shows all routes
   - Metrics integration with Prometheus
   - Access logs for debugging

### For Development Workflow

1. **Fast Iteration**
   - `docker compose up` immediately accessible
   - No proxy restarts needed
   - Labels declare routing intent

2. **Clean Port Management**
   - Only ports 80/443/8080 exposed on host
   - No port conflicts between projects
   - Services communicate via Docker networks

3. **Certificate Management**
   - Single wildcard cert at edge
   - Backend services can use HTTP
   - Traefik handles SSL termination

## 🎯 Success Criteria

After migration:
- ✅ All `*.ravenhelm.test` routes through Traefik
- ✅ No port conflicts between stacks
- ✅ Services discoverable via Docker labels
- ✅ SSL termination at edge only
- ✅ Network isolation per stack
- ✅ Traefik dashboard accessible
- ✅ Zero manual nginx configuration

## 📝 Helper Scripts

### Create Networks Script

`scripts/create_traefik_networks.sh`:
```bash
#!/bin/bash
networks=(
  "edge:10.0.10.0/24"
  "platform_net:10.10.0.0/24"
  "gitlab_net:10.20.0.0/24"
  "saaa_net:10.30.0.0/24"
  "m2c_net:10.40.0.0/24"
  "tinycrm_net:10.50.0.0/24"
)

for net in "${networks[@]}"; do
  name="${net%%:*}"
  subnet="${net##*:}"
  
  if ! docker network inspect "$name" >/dev/null 2>&1; then
    echo "Creating network $name ($subnet)..."
    docker network create --driver bridge --subnet "$subnet" "$name"
  else
    echo "Network $name already exists"
  fi
done
```

### Check Traefik Routes

`scripts/check_traefik_routes.sh`:
```bash
#!/bin/bash
echo "Traefik Routes:"
curl -s http://localhost:8080/api/http/routers | jq -r '.[] | "\(.name): \(.rule)"'
```

## 🔄 Rollback Plan

If issues occur:

1. **Keep old nginx configs in git**
2. **Stop Traefik**: `cd traefik-edge && docker compose down`
3. **Revert docker-compose.yml changes**
4. **Restore port mappings**
5. **Start old nginx proxies**

## 📚 Next Steps

1. Review and approve this migration plan
2. Create `/Users/nwalker/Development/hlidskjalf/traefik-edge/` directory structure
3. Test Traefik edge proxy setup
4. Migrate one service (e.g., Grafana) as proof of concept
5. Gradually migrate remaining services
6. Update Norns orchestration to understand Traefik labels
7. Decommission `ravenhelm-proxy` once migration complete

---

**The Cognitive Spine meets Automatic Service Discovery!** 🚀

*"The ravens need not remember the paths—Traefik discovers them automatically."*

