# RUNBOOK-002: Add Domain to Traefik

> **Category:** Infrastructure  
> **Priority:** Standard Change  
> **Last Updated:** 2024-12-03

---

## Prerequisites

- [ ] Service already deployed (see [RUNBOOK-001](./RUNBOOK-001-deploy-docker-service.md))
- [ ] Port registry updated
- [ ] dnsmasq resolving `*.ravenhelm.test` → 127.0.0.1

---

## Option A: Docker Labels (Autodiscovery)

Traefik automatically discovers services with proper labels. Add these to your service:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.docker.network=platform_net"
  
  # HTTP Router
  - "traefik.http.routers.my-service.rule=Host(`my-service.ravenhelm.test`)"
  - "traefik.http.routers.my-service.entrypoints=websecure"
  - "traefik.http.routers.my-service.tls=true"
  
  # Load Balancer
  - "traefik.http.services.my-service.loadbalancer.server.port=8080"
  
  # Optional: Middlewares
  - "traefik.http.routers.my-service.middlewares=secure-headers@file"
```

**Apply:**
```bash
docker compose up -d my-service
```

---

## Option B: Dynamic Configuration (File-based)

For services not managed by Docker Compose, edit `ravenhelm-proxy/dynamic.yml`:

```yaml
http:
  routers:
    my-service:
      rule: "Host(`my-service.ravenhelm.test`)"
      service: "my-service"
      entrypoints:
        - websecure
      tls: {}
      middlewares:
        - secure-headers

  services:
    my-service:
      loadBalancer:
        servers:
          - url: "http://host.docker.internal:8080"  # Or Docker service name
```

**Reload Traefik:**
```bash
# Traefik watches dynamic.yml, but you can force reload:
docker compose restart traefik
```

---

## Verify Routing

```bash
# Test the route
curl -sk https://my-service.ravenhelm.test:8443/ | head

# Check Traefik API (if dashboard enabled)
curl -s http://localhost:8080/api/http/routers | jq '.[] | select(.name | contains("my-service"))'
```

---

## Subdomain Patterns

| Pattern | Example | Use Case |
|---------|---------|----------|
| `service.ravenhelm.test` | `grafana.ravenhelm.test` | Direct service |
| `service.observe.ravenhelm.test` | `langfuse.observe.ravenhelm.test` | Observability stack |
| `service.events.ravenhelm.test` | `console.events.ravenhelm.test` | Event plane |
| `*.project.ravenhelm.test` | `api.myapp.ravenhelm.test` | Project-specific |

---

## Common Middlewares

```yaml
http:
  middlewares:
    # Security headers
    secure-headers:
      headers:
        stsSeconds: 31536000
        forceSTSHeader: true
        contentTypeNosniff: true
        browserXssFilter: true
    
    # Rate limiting
    rate-limit:
      rateLimit:
        average: 100
        burst: 200
        period: 1s
    
    # Basic auth (temporary, prefer Zitadel)
    basic-auth:
      basicAuth:
        users:
          - "admin:$apr1$..."  # htpasswd generated
    
    # Forward auth to Zitadel
    zitadel-auth:
      forwardAuth:
        address: "http://zitadel:8080/auth/validate"
        trustForwardHeader: true
```

---

## WebSocket Support

For services using WebSockets:

```yaml
labels:
  - "traefik.http.routers.my-ws.rule=Host(`my-service.ravenhelm.test`) && PathPrefix(`/ws`)"
  - "traefik.http.routers.my-ws.entrypoints=websecure"
  - "traefik.http.routers.my-ws.tls=true"
  - "traefik.http.services.my-ws.loadbalancer.server.port=8080"
  # WebSocket-specific
  - "traefik.http.middlewares.my-ws-upgrade.headers.customRequestHeaders.Connection=Upgrade"
  - "traefik.http.middlewares.my-ws-upgrade.headers.customRequestHeaders.Upgrade=websocket"
  - "traefik.http.routers.my-ws.middlewares=my-ws-upgrade"
```

---

## Troubleshooting

### Route Not Working

```bash
# Check Traefik sees the container
docker compose logs traefik | grep "my-service"

# Verify network
docker network inspect platform_net | jq '.[0].Containers'

# Test directly (bypass Traefik)
curl http://localhost:8080/health  # Direct container port
```

### TLS Certificate Issues

```bash
# Verify certificate includes domain
openssl s_client -connect my-service.ravenhelm.test:8443 -servername my-service.ravenhelm.test 2>/dev/null | openssl x509 -text | grep DNS
```

### DNS Not Resolving

```bash
# Check dnsmasq
dig my-service.ravenhelm.test @127.0.0.1 -p 15353

# Flush DNS cache
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
```

---

## References

- [RUNBOOK-001: Deploy Docker Service](./RUNBOOK-001-deploy-docker-service.md)
- [RUNBOOK-003: Generate Certificates](./RUNBOOK-003-generate-certificates.md)
- [Traefik Documentation](https://doc.traefik.io/traefik/)

