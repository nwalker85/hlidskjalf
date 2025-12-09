# RUNBOOK-026: Let's Encrypt External HTTPS Setup

**Status**: Active  
**Owner**: Platform Team  
**Last Updated**: 2025-12-06

## Overview

This runbook documents the configuration and operation of Let's Encrypt certificates for staging `.ravenhelm.dev` domains, enabling multi-environment support.

## Environment Strategy

- **`.test`** - Development (local, self-signed certificates)
- **`.dev`** - Staging (public, Let's Encrypt certificates)
- **`.ai`** - Production (future, Let's Encrypt certificates)

## Architecture

### Multi-Environment Strategy

- **Development (`.test`)**: Self-signed certificates, oauth2-proxy on port 4180
- **Staging (`.dev`)**: Let's Encrypt certificates, oauth2-proxy-staging on port 4181
- **Production (`.ai`)**: Future - Let's Encrypt certificates, oauth2-proxy-prod on port 4182

### Components

1. **Traefik** - Single ingress with Let's Encrypt certificate resolver
2. **OAuth2-Proxy** - Two instances for domain-specific authentication
3. **Zitadel** - Identity provider accessible on both domains
4. **Let's Encrypt** - Automated certificate issuance via HTTP-01 challenge

## Configuration Files

### Primary Files

- `/Users/nwalker/Development/hlidskjalf/ravenhelm-proxy/traefik.yml` - Certificate resolver config
- `/Users/nwalker/Development/hlidskjalf/ravenhelm-proxy/dynamic.yml` - Router and middleware definitions
- `/Users/nwalker/Development/hlidskjalf/ravenhelm-proxy/docker-compose-traefik.yml` - Traefik container config
- `/Users/nwalker/Development/hlidskjalf/docker-compose.yml` - OAuth2-proxy-dev service
- `/Users/nwalker/Development/hlidskjalf/compose/docker-compose.security.yml` - Modular oauth2-proxy-dev

### Certificate Storage

- **Volume**: `traefik_letsencrypt`
- **Path**: `/letsencrypt/acme.json` (inside Traefik container)
- **Permissions**: 600, owned by container user

## Staging Services

The following services are exposed on staging (`.ravenhelm.dev`):

| Service | Domain | Auth Method | Router Name |
|---------|--------|-------------|-------------|
| Hliðskjálf UI | `hlidskjalf.ravenhelm.dev` | Native NextAuth/Zitadel | `hlidskjalf-ui-dev` |
| Hliðskjálf API | `hlidskjalf-api.ravenhelm.dev` | OAuth2-Proxy forward auth | `hlidskjalf-api-dev` |
| Grafana | `grafana.ravenhelm.dev` | Native Zitadel SSO | `grafana-dev` |
| Zitadel | `zitadel.ravenhelm.dev` | N/A (is the auth provider) | `zitadel-dev` |
| OAuth2-Proxy | `auth.ravenhelm.dev` | N/A (provides auth) | `oauth2-proxy-dev` |

## Prerequisites

### DNS Configuration

Ensure DNS A records point to your public IP:

```bash
dig +short hlidskjalf.ravenhelm.dev
dig +short auth.ravenhelm.dev
dig +short zitadel.ravenhelm.dev
dig +short grafana.ravenhelm.dev
dig +short hlidskjalf-api.ravenhelm.dev
```

All should return your public IP address.

### Port Forwarding

Required ports on your router/firewall:

- **Port 80** → This machine (required for Let's Encrypt HTTP-01 challenge)
- **Port 443** → This machine (HTTPS traffic)

Verify:

```bash
# Check ports are bound
sudo lsof -i :80
sudo lsof -i :443

# Test external accessibility (from outside your network)
curl -I http://hlidskjalf.ravenhelm.dev
```

### Environment Variables

Required in `.env` or environment:

```bash
# OAuth2-Proxy for .dev domain
OAUTH2_PROXY_DEV_CLIENT_ID=<zitadel-client-id>
OAUTH2_PROXY_DEV_CLIENT_SECRET=<zitadel-client-secret>
OAUTH2_PROXY_COOKIE_SECRET=<shared-cookie-secret>

# OAuth2-Proxy for .test domain (existing)
OAUTH2_PROXY_CLIENT_ID=<zitadel-client-id>
OAUTH2_PROXY_CLIENT_SECRET=<zitadel-client-secret>
```

## Initial Setup

### Step 1: Configure Zitadel Applications

Create or update Zitadel applications to include `.dev` redirect URIs:

**OAuth2-Proxy Application:**
- Add `https://auth.ravenhelm.dev/oauth2/callback`
- Add `https://hlidskjalf.ravenhelm.dev/*`
- Add `https://hlidskjalf-api.ravenhelm.dev/*`

**Grafana Application:**
- Add `https://grafana.ravenhelm.dev/login/generic_oauth`

**Hliðskjálf UI Application:**
- Add `https://hlidskjalf.ravenhelm.dev/api/auth/callback/zitadel`

### Step 2: Deploy with Staging Certificates

The configuration starts with Let's Encrypt staging to avoid rate limits:

```yaml
# In traefik.yml
certificatesResolvers:
  letsencrypt:
    acme:
      email: nathan@ravenhelm.dev
      storage: /letsencrypt/acme.json
      caServer: https://acme-staging-v02.api.letsencrypt.org/directory
      httpChallenge:
        entryPoint: web
```

Deploy:

```bash
cd /Users/nwalker/Development/hlidskjalf/ravenhelm-proxy
docker compose down
docker compose up -d
```

### Step 3: Verify Staging Certificates

Check Traefik logs:

```bash
docker logs ravenhelm-traefik -f
```

Look for:
- `Domains ["hlidskjalf.ravenhelm.dev"] need ACME certificates generation`
- `authz: https://acme-staging-v02.api.letsencrypt.org/...`
- `The certificate obtained for 'hlidskjalf.ravenhelm.dev' is valid`

Test in browser (expect certificate warning for staging):

```bash
curl -I https://hlidskjalf.ravenhelm.dev
```

### Step 4: Switch from Staging to Production Let's Encrypt

Once Let's Encrypt staging certificates work, switch to production Let's Encrypt CA:

1. Edit `traefik.yml` and remove or comment the `caServer` line:

```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      email: nathan@ravenhelm.dev
      storage: /letsencrypt/acme.json
      # caServer: https://acme-staging-v02.api.letsencrypt.org/directory  # REMOVED
      httpChallenge:
        entryPoint: web
```

2. Clear staging certificates:

```bash
docker compose down
docker volume rm ravenhelm-proxy_traefik_letsencrypt
docker compose up -d
```

3. Verify production Let's Encrypt certificates:

```bash
# Check certificate issuer
echo | openssl s_client -connect hlidskjalf.ravenhelm.dev:443 2>/dev/null | openssl x509 -noout -issuer

# Should show: issuer=C = US, O = Let's Encrypt, CN = R3
```

## Operations

### Checking Certificate Status

```bash
# View acme.json contents
docker exec ravenhelm-traefik cat /letsencrypt/acme.json | jq .

# Check certificate expiration
echo | openssl s_client -connect hlidskjalf.ravenhelm.dev:443 2>/dev/null | openssl x509 -noout -dates
```

### Manual Certificate Renewal

Traefik automatically renews certificates 30 days before expiration. To force renewal:

```bash
# Delete acme.json and restart
docker compose down
docker volume rm ravenhelm-proxy_traefik_letsencrypt
docker compose up -d
```

### Troubleshooting

#### Certificate Not Issued

**Symptoms**: Browser shows self-signed certificate warning

**Checks**:

```bash
# 1. Verify DNS resolves to public IP
dig +short hlidskjalf.ravenhelm.dev

# 2. Verify port 80 is accessible externally
curl -I http://hlidskjalf.ravenhelm.dev/.well-known/acme-challenge/test

# 3. Check Traefik logs for ACME errors
docker logs ravenhelm-traefik --tail 100 | grep -i acme

# 4. Verify router configuration
docker exec ravenhelm-traefik cat /etc/traefik/dynamic.yml | grep -A 5 "hlidskjalf-ui-dev"
```

**Common Issues**:
- Port 80 not forwarded → Configure router
- DNS not propagated → Wait 5-10 minutes
- Rate limit hit → Use staging, wait 1 hour
- Wrong email → Update `traefik.yml`

#### OAuth Flow Fails

**Symptoms**: Redirect loop or "unauthorized" errors

**Checks**:

```bash
# 1. Verify oauth2-proxy-dev is running
docker ps | grep oauth2-proxy-dev

# 2. Check oauth2-proxy-dev logs
docker logs gitlab-sre-oauth2-proxy-dev --tail 50

# 3. Verify Zitadel redirect URIs
# Access https://zitadel.ravenhelm.dev/ui/console
# Check application settings

# 4. Test oauth2-proxy health
curl -I http://localhost:4181/ping
```

**Common Issues**:
- Missing `OAUTH2_PROXY_DEV_CLIENT_ID` → Add to `.env`
- Zitadel redirect URI mismatch → Update in Zitadel console
- Cookie domain mismatch → Verify `OAUTH2_PROXY_COOKIE_DOMAINS=.ravenhelm.dev`

#### Mixed Content Warnings

**Symptoms**: Browser console shows "Mixed Content" errors

**Fix**: Ensure all backend services use HTTPS or are proxied through Traefik:

```yaml
# In dynamic.yml, verify service URLs
services:
  hlidskjalf-ui-svc:
    loadBalancer:
      servers:
        - url: "http://host.docker.internal:3900"  # OK - Traefik terminates TLS
```

## Let's Encrypt Rate Limits

Production Let's Encrypt CA limits:

- **50 certificates per registered domain per week**
- **5 duplicate certificates per week**
- **300 new orders per account per 3 hours**

Use Let's Encrypt staging for testing to avoid hitting limits.

## Security Considerations

### Certificate Backup

The `acme.json` file contains private keys. Back it up securely:

```bash
# Backup
docker run --rm -v ravenhelm-proxy_traefik_letsencrypt:/data \
  -v $(pwd):/backup alpine tar czf /backup/letsencrypt-backup.tar.gz /data

# Restore
docker run --rm -v ravenhelm-proxy_traefik_letsencrypt:/data \
  -v $(pwd):/backup alpine tar xzf /backup/letsencrypt-backup.tar.gz -C /
```

### SPIRE/mTLS Considerations

- Staging `.dev` endpoints use **TLS only** (Let's Encrypt certificates)
- Development `.test` endpoints continue using **SPIRE mTLS** for service-to-service
- Production `.ai` endpoints will use **TLS only** (Let's Encrypt certificates)
- Traefik routes appropriately based on domain

### File Permissions

Per RUNBOOK-005, all platform files should be owned by `ravenhelm:ravenhelm` (UID/GID 1001). The `acme.json` file inside the container is managed by Traefik's user.

## Monitoring

### Metrics

Traefik exposes Prometheus metrics on port 8888:

```bash
curl http://localhost:8888/metrics | grep traefik_tls
```

### Alerts

Consider adding alerts for:
- Certificate expiration < 14 days
- ACME challenge failures
- OAuth2-proxy health check failures

## Related Documentation

- [RUNBOOK-024: Add Shared Service](RUNBOOK-024-add-shared-service.md) - Adding new services to Traefik
- [RUNBOOK-005: File Ownership & Permissions](RUNBOOK-005-file-ownership-permissions.md) - Platform ownership model
- [Traefik Autodiscovery Runbook](ravenhelm-traefik-autodiscovery.md) - Traefik architecture
- [Port Registry](/Users/nwalker/Development/hlidskjalf/config/port_registry.yaml) - Port 4180/4181 assignments

## Rollback Procedure

To revert to dev-only `.test` domains (disable staging):

1. Stop oauth2-proxy-dev:

```bash
docker stop gitlab-sre-oauth2-proxy-dev
docker rm gitlab-sre-oauth2-proxy-dev
```

2. Remove `.dev` routers from `dynamic.yml`:

```bash
# Comment out or delete all routers with `-dev` suffix
```

3. Remove Let's Encrypt resolver from `traefik.yml`:

```bash
# Comment out certificatesResolvers section
```

4. Restart Traefik:

```bash
cd /Users/nwalker/Development/hlidskjalf/ravenhelm-proxy
docker compose restart traefik
```

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2025-12-06 | Platform Team | Initial creation - staging environment HTTPS setup |

