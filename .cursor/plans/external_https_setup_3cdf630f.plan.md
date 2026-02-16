---
name: External HTTPS Setup
overview: Configure Traefik to support both internal (*.ravenhelm.test) and external (*.ravenhelm.dev) domains with Let's Encrypt certificates for public HTTPS access.
todos: []
---

# Configure External HTTPS Access for ravenhelm.dev

Enable dual-domain support with Let's Encrypt certificates for public access while maintaining internal .test domains.

## 1. Configure Let's Encrypt in Traefik

Update [`ravenhelm-proxy/traefik.yml`](ravenhelm-proxy/traefik.yml) to add Let's Encrypt certificate resolver:

- Add `certificatesResolvers` section with HTTP-01 challenge
- Configure email for Let's Encrypt notifications
- Set up staging environment first to avoid rate limits
- Configure storage file for certificate persistence
```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      email: your-email@example.com  # Required for notifications
      storage: /letsencrypt/acme.json
      httpChallenge:
        entryPoint: web
```


## 2. Add Let's Encrypt Storage Volume

Update [`ravenhelm-proxy/docker-compose-traefik.yml`](ravenhelm-proxy/docker-compose-traefik.yml):

- Add persistent volume for ACME certificate storage
- Mount the volume at `/letsencrypt` in the Traefik container
- Ensure proper permissions (600) on acme.json

## 3. Duplicate Key Service Routers for .dev Domain

Update [`ravenhelm-proxy/dynamic.yml`](ravenhelm-proxy/dynamic.yml) to add .dev routers for public services:

**Primary services to expose:**

- `hlidskjalf-ui` → `hlidskjalf.ravenhelm.dev`
- `hlidskjalf-api` → `hlidskjalf-api.ravenhelm.dev`
- `grafana` → `grafana.ravenhelm.dev`
- `zitadel` → `zitadel.ravenhelm.dev` (required for SSO)
- `oauth2-proxy` → `auth.ravenhelm.dev` (required for auth flow)

For each service, add a new router with:

- Host rule matching `.ravenhelm.dev`
- `tls.certResolver: letsencrypt`
- Same service backend and middlewares as .test version

Example pattern:

```yaml
hlidskjalf-ui-dev:
  rule: "Host(`hlidskjalf.ravenhelm.dev`)"
  service: hlidskjalf-ui-svc
  middlewares:
    - secure-headers
  tls:
    certResolver: letsencrypt
```

## 4. Update OAuth2-Proxy Configuration

The oauth2-proxy needs to know about the new `.dev` domain:

- Update cookie domain to support both `.ravenhelm.test` and `.ravenhelm.dev`
- Add `https://hlidskjalf.ravenhelm.dev` to allowed redirect URLs in Zitadel
- Update oauth2-proxy `--whitelist-domain` configuration

## 5. Update Zitadel Redirect URIs

In Zitadel console or via API:

- Add `https://hlidskjalf.ravenhelm.dev/*` to allowed redirect URIs
- Add `https://auth.ravenhelm.dev/*` to oauth2-proxy application
- Add `https://grafana.ravenhelm.dev/*` for Grafana SSO

## 6. Verify DNS and Port Forwarding

Before testing, ensure:

- DNS A record for `*.ravenhelm.dev` points to your public IP
- Port 80 is forwarded to this machine (required for Let's Encrypt HTTP-01)
- Port 443 is forwarded to this machine (for HTTPS traffic)
- Firewall allows inbound traffic on ports 80 and 443

## 7. Test Let's Encrypt Certificate Issuance

Start with staging to avoid rate limits:

1. Use `caServer: https://acme-staging-v02.api.letsencrypt.org/directory` initially
2. Access `https://hlidskjalf.ravenhelm.dev` and verify certificate issuance
3. Check Traefik logs for ACME challenge completion
4. Once verified, switch to production Let's Encrypt endpoint

## 8. Switch to Production Certificates

After successful staging test:

- Remove or comment out staging `caServer` setting
- Delete staging certificates from `acme.json`
- Restart Traefik to issue production certificates
- Verify browser shows valid certificate from Let's Encrypt

## Files to Modify

- [`ravenhelm-proxy/traefik.yml`](ravenhelm-proxy/traefik.yml) - Add Let's Encrypt resolver
- [`ravenhelm-proxy/dynamic.yml`](ravenhelm-proxy/dynamic.yml) - Add .dev routers
- [`ravenhelm-proxy/docker-compose-traefik.yml`](ravenhelm-proxy/docker-compose-traefik.yml) - Add volume
- OAuth2-proxy configuration (location TBD based on current setup)
- Zitadel redirect URI configuration (manual update via UI or script)

## Success Criteria

- `https://hlidskjalf.ravenhelm.dev` loads with valid Let's Encrypt certificate
- No browser certificate warnings
- SSO authentication flow works via `.dev` domain
- Internal `.test` domains continue to work unchanged