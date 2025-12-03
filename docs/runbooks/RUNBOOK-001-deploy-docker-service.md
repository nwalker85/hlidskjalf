# RUNBOOK-001: Deploy New Docker Service

> **Category:** Infrastructure  
> **Priority:** Standard Change  
> **Last Updated:** 2024-12-03

---

## Prerequisites Checklist

Before deploying ANY new Docker service, verify:

- [ ] **Port Registry Checked**: No port conflicts in `config/port_registry.yaml`
- [ ] **Network Defined**: Service uses appropriate Docker network
- [ ] **Traefik Labels**: Service has proper routing labels
- [ ] **Certificates Valid**: mkcert certificate includes required domain
- [ ] **Health Check**: Service has Docker health check defined

---

## Step 1: Check Port Registry

```bash
# View current port allocations
cat config/port_registry.yaml | grep -A5 "your-service"

# Run port conflict check
python scripts/check_ports.py
```

**If port conflict exists:** Choose a different port from the available range:
- Platform services: 8000-8099
- Personal projects: 8100-8199
- Work projects: 8200-8299
- Metrics/monitoring: 9000-9999

---

## Step 2: Update Port Registry

Add your service to `config/port_registry.yaml`:

```yaml
services:
  your-service:
    project: ravenhelm
    port: 8XXX
    internal_port: 8080
    environment: dev
    description: "Your service description"
    traefik_domain: "your-service.ravenhelm.test"
```

---

## Step 3: Add Traefik Labels

In `docker-compose.yml`, add these labels to your service:

```yaml
services:
  your-service:
    image: your-image:latest
    container_name: gitlab-sre-your-service
    networks:
      - gitlab-network
      - platform_net  # For Traefik routing
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=platform_net"
      - "traefik.http.routers.your-service.rule=Host(`your-service.ravenhelm.test`)"
      - "traefik.http.routers.your-service.entrypoints=websecure"
      - "traefik.http.routers.your-service.tls=true"
      - "traefik.http.services.your-service.loadbalancer.server.port=8080"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

---

## Step 4: Update Certificates (if new domain)

If adding a new subdomain, regenerate certificates:

```bash
cd ravenhelm-proxy/config/certs

mkcert -cert-file server.crt -key-file server.key \
  ravenhelm.test \
  "*.ravenhelm.test" \
  "*.observe.ravenhelm.test" \
  "*.events.ravenhelm.test" \
  vault.ravenhelm.test \
  localstack.ravenhelm.test \
  "*.saaa.ravenhelm.test" \
  "*.agentcrucible.ravenhelm.test" \
  your-service.ravenhelm.test  # Add new domain

# Restart Traefik to pick up new certs
docker compose restart traefik
```

---

## Step 5: Deploy Service

```bash
# Build (if custom image)
docker compose build your-service

# Deploy
docker compose up -d your-service

# Verify health
docker compose ps your-service
docker compose logs your-service --tail 20
```

---

## Step 6: Verify Routing

```bash
# Test via Traefik
curl -sk https://your-service.ravenhelm.test:8443/health

# Check Traefik dashboard (if enabled)
open http://localhost:8080/dashboard/
```

---

## Step 7: Update Documentation

- [ ] Add service to README.md service table
- [ ] Update port_registry.yaml (already done in Step 2)
- [ ] Add any new runbooks for service-specific operations

---

## Rollback Procedure

If deployment fails:

```bash
# Stop the service
docker compose stop your-service

# Remove if needed
docker compose rm -f your-service

# Revert port_registry.yaml changes
git checkout config/port_registry.yaml
```

---

## Common Issues

### Port Already in Use
```bash
# Find what's using the port
lsof -i :8XXX

# Kill if safe
kill -9 <PID>
```

### Traefik Not Routing
```bash
# Check Traefik logs
docker compose logs traefik --tail 50

# Verify labels
docker inspect gitlab-sre-your-service | jq '.[0].Config.Labels'

# Ensure service is on platform_net
docker network inspect platform_net | jq '.[0].Containers'
```

### Certificate Errors
```bash
# Verify certificate includes domain
openssl x509 -in ravenhelm-proxy/config/certs/server.crt -text | grep -A1 "Subject Alternative Name"
```

---

## References

- [RUNBOOK-002: Add Domain to Traefik](./RUNBOOK-002-add-traefik-domain.md)
- [RUNBOOK-003: Generate Certificates](./RUNBOOK-003-generate-certificates.md)
- [Port Registry](../../config/port_registry.yaml)

