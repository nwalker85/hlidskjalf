# RUNBOOK-003: Generate/Update Certificates

> **Category:** Infrastructure  
> **Priority:** Standard Change  
> **Last Updated:** 2024-12-03

---

## Prerequisites

- [ ] mkcert installed: `brew install mkcert nss`
- [ ] CA installed: `mkcert -install`
- [ ] Know all domains that need to be included

---

## Step 1: List Current Domains

Check what domains are currently in use:

```bash
# From port registry
grep "traefik_domain" config/port_registry.yaml | awk '{print $2}'

# From Traefik dynamic config
grep -E "Host\(" ravenhelm-proxy/dynamic.yml | sed 's/.*Host(`\([^`]*\).*/\1/'

# From docker-compose labels
grep -E "traefik.*rule.*Host" docker-compose.yml | sed 's/.*Host(`\([^`]*\).*/\1/'
```

---

## Step 2: Generate New Certificate

```bash
cd ravenhelm-proxy/config/certs

# Full command with all current domains
mkcert -cert-file server.crt -key-file server.key \
  ravenhelm.test \
  "*.ravenhelm.test" \
  "*.observe.ravenhelm.test" \
  "*.events.ravenhelm.test" \
  "*.saaa.ravenhelm.test" \
  "*.agentcrucible.ravenhelm.test" \
  vault.ravenhelm.test \
  localstack.ravenhelm.test \
  norns.ravenhelm.test \
  hlidskjalf.ravenhelm.test \
  ollama.ravenhelm.test \
  memgraph.ravenhelm.test \
  neo4j.ravenhelm.test \
  zitadel.ravenhelm.test
```

---

## Step 3: Verify Certificate

```bash
# Check SANs (Subject Alternative Names)
openssl x509 -in server.crt -text -noout | grep -A1 "Subject Alternative Name"

# Should show all domains like:
# DNS:ravenhelm.test, DNS:*.ravenhelm.test, DNS:*.observe.ravenhelm.test, ...
```

---

## Step 4: Distribute to Services

Some services need their own copy of the certificate:

```bash
# Copy to observability nginx
cp server.crt server.key ../../observability/config/certs/ 2>/dev/null || true

# Copy to vault nginx  
cp server.crt server.key ../../openbao/config/certs/ 2>/dev/null || true

# Copy to main config
cp server.crt server.key ../../config/certs/
```

---

## Step 5: Reload Services

```bash
# Restart Traefik (if running)
cd /Users/nwalker/Development/hlidskjalf
docker compose restart traefik 2>/dev/null || true

# Restart ravenhelm-proxy nginx
cd ravenhelm-proxy && docker compose restart nginx && cd ..

# Restart any nginx sidecars
docker compose restart observe-nginx vault-nginx events-nginx 2>/dev/null || true
```

---

## Step 6: Verify TLS

```bash
# Test a domain
curl -v https://hlidskjalf.ravenhelm.test:8443/ 2>&1 | grep -E "(SSL|TLS|certificate)"

# Should show: SSL certificate verify ok
```

---

## Automation Script

Save as `scripts/certs/regenerate.sh`:

```bash
#!/bin/bash
set -e

cd "$(dirname "$0")/../../ravenhelm-proxy/config/certs"

echo "📜 Generating new certificates..."

# Read domains from port_registry.yaml
DOMAINS=$(cat ../../../config/port_registry.yaml | grep traefik_domain | awk '{print $2}' | sort -u)

# Base domains
BASE_DOMAINS=(
  "ravenhelm.test"
  "*.ravenhelm.test"
  "*.observe.ravenhelm.test"
  "*.events.ravenhelm.test"
  "*.saaa.ravenhelm.test"
  "*.agentcrucible.ravenhelm.test"
)

# Combine and generate
ALL_DOMAINS="${BASE_DOMAINS[@]} $DOMAINS"
mkcert -cert-file server.crt -key-file server.key $ALL_DOMAINS

echo "✅ Certificate generated with $(echo $ALL_DOMAINS | wc -w) domains"

# Copy to other locations
cp server.crt server.key ../../config/certs/

echo "📋 Restart services to pick up new certs:"
echo "   docker compose restart traefik nginx"
```

---

## When to Regenerate

- Adding a new service with a unique subdomain
- Certificate expired (mkcert certs last ~2 years)
- Changing domain structure
- After mkcert CA reinstall

---

## Troubleshooting

### Browser Still Shows Old Cert

```bash
# Clear browser TLS cache
# Chrome: chrome://net-internals/#sockets → Flush socket pools

# macOS: Restart mDNSResponder
sudo killall -HUP mDNSResponder
```

### mkcert CA Not Trusted

```bash
# Reinstall CA
mkcert -install

# Verify in Keychain Access
security dump-trust-settings -d | grep mkcert
```

### Certificate Doesn't Include Domain

Regenerate with the domain explicitly listed. Wildcards don't cover nested subdomains:
- `*.ravenhelm.test` covers `foo.ravenhelm.test`
- BUT NOT `foo.bar.ravenhelm.test` (needs separate entry)

---

## References

- [mkcert Documentation](https://github.com/FiloSottile/mkcert)
- [RUNBOOK-002: Add Traefik Domain](./RUNBOOK-002-add-traefik-domain.md)

