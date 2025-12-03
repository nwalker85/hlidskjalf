# RUNBOOK-004: SPIRE Management

> **Purpose**: Bootstrap, manage, and troubleshoot SPIRE for mTLS  
> **Scope**: Zero Trust service-to-service authentication  
> **Priority**: 🔴 CRITICAL — Security foundation

---

## Overview

SPIRE (SPIFFE Runtime Environment) provides:
- **Workload Identity**: Every service gets a cryptographic identity (SVID)
- **mTLS**: All service-to-service communication is encrypted and authenticated
- **Zero Trust**: No implicit trust — every connection is verified

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     TRUST DOMAIN: ravenhelm.local               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐           ┌──────────────────┐            │
│  │   SPIRE Server   │           │   SPIRE Agent    │            │
│  │    :8081         │◀─────────▶│                  │            │
│  │                  │           │  Docker Attester │            │
│  │  - Issues SVIDs  │           │  - Attests via   │            │
│  │  - Manages trust │           │    container     │            │
│  │  - Entry store   │           │    labels        │            │
│  └──────────────────┘           └────────┬─────────┘            │
│                                          │                       │
│                            Workload API Socket                   │
│                         /tmp/spire-agent/public/api.sock         │
│                                          │                       │
│         ┌───────────────┬───────────────┼───────────────┐       │
│         ▼               ▼               ▼               ▼       │
│    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    │
│    │Postgres │    │  Redis  │    │  NATS   │    │ Grafana │    │
│    │         │    │         │    │         │    │         │    │
│    │ SVID    │    │ SVID    │    │ SVID    │    │ SVID    │    │
│    └─────────┘    └─────────┘    └─────────┘    └─────────┘    │
│                                                                  │
│            All connections use mTLS with SVID certs              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- [ ] Docker and Docker Compose installed
- [ ] OpenSSL available for CA generation
- [ ] `docker-compose.yml` includes SPIRE services
- [ ] Network connectivity between services

---

## 1. Initial Bootstrap

### Step 1.1: Generate Upstream CA

The upstream CA is the root of trust for SPIRE.

```bash
cd ~/Development/hlidskjalf

# Generate the upstream CA (run ONCE)
./spire/init-spire.sh ca
```

**Verify:**
```bash
ls -la spire/server/dummy_upstream_ca.*
# Should see:
#   dummy_upstream_ca.crt
#   dummy_upstream_ca.key
```

### Step 1.2: Start SPIRE Server

```bash
# Start SPIRE server
docker compose up -d spire-server

# Wait for health
docker compose logs -f spire-server
# Look for: "Server is ready"

# Verify health
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server healthcheck
# Expected: Server is healthy
```

### Step 1.3: Start SPIRE Agent

```bash
# Start SPIRE agent (depends on server being healthy)
docker compose up -d spire-agent

# Check logs
docker compose logs -f spire-agent
# Look for: "Agent is ready"

# Verify health
docker exec gitlab-sre-spire-agent /opt/spire/bin/spire-agent healthcheck
# Expected: Agent is healthy
```

### Step 1.4: Bootstrap Workloads

```bash
# Bootstrap (generates join token, registers workloads)
./spire/init-spire.sh bootstrap
```

**This registers:**
- gitlab
- postgres
- redis
- nats
- otel-collector
- prometheus
- grafana
- langfuse
- redpanda
- openbao
- localstack
- ravenhelm-control (Hliðskjálf)

---

## 2. Workload Registration

### 2.1: Register a New Workload

```bash
# Register a new workload
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry create \
    -parentID spiffe://ravenhelm.local/agent/local \
    -spiffeID spiffe://ravenhelm.local/workload/my-service \
    -selector docker:label:ravenhelm.workload:my-service
```

### 2.2: Registration with Multiple Selectors

```bash
# More specific registration (project + service)
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry create \
    -parentID spiffe://ravenhelm.local/agent/local \
    -spiffeID spiffe://ravenhelm.local/workload/myproject/api \
    -selector docker:label:ravenhelm.project:myproject \
    -selector docker:label:ravenhelm.service:api
```

### 2.3: Required Docker Labels

For a workload to be attested, it needs labels in docker-compose:

```yaml
services:
  my-service:
    image: my-image
    labels:
      - "ravenhelm.project=myproject"
      - "ravenhelm.service=api"
      - "ravenhelm.workload=my-service"  # Must match selector
```

### 2.4: List Registered Entries

```bash
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry show
```

### 2.5: Delete an Entry

```bash
# Get entry ID first
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry show

# Delete by ID
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry delete \
    -entryID <entry-id>
```

---

## 3. SVID Management

### 3.1: Fetch SVID for a Workload

From within a container that has access to the SPIRE agent socket:

```bash
# Using spire-agent CLI
/opt/spire/bin/spire-agent api fetch x509 \
    -socketPath /tmp/spire-agent/public/api.sock
```

### 3.2: SVID Auto-Rotation

SVIDs are automatically rotated by SPIRE:
- Default TTL: 1 hour (`default_x509_svid_ttl` in server.conf)
- Rotation happens at ~50% of TTL

### 3.3: Manual SVID Refresh

Workloads should implement SVID watching. For debugging:

```bash
# Force agent to re-attest
docker restart gitlab-sre-spire-agent
```

---

## 4. Service Configuration for mTLS

### 4.1: NATS with SPIRE

Update NATS configuration to use SPIRE SVIDs:

```yaml
# nats-server.conf
tls {
    cert_file: "/run/spire/svids/svid.pem"
    key_file: "/run/spire/svids/key.pem"
    ca_file: "/run/spire/svids/bundle.pem"
    verify: true
}
```

### 4.2: PostgreSQL with SPIRE

```yaml
# postgresql.conf
ssl = on
ssl_cert_file = '/run/spire/svids/svid.pem'
ssl_key_file = '/run/spire/svids/key.pem'
ssl_ca_file = '/run/spire/svids/bundle.pem'
```

### 4.3: Python Client with SPIFFE

```python
from spiffe import SpiffeWorkloadAPIClient
from spiffe.svid.x509_svid import X509Svid

# Connect to SPIRE agent
client = SpiffeWorkloadAPIClient(
    socket_path="/tmp/spire-agent/public/api.sock"
)

# Fetch SVID
svid: X509Svid = client.fetch_x509_svid()

# Use for mTLS
import ssl
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.load_cert_chain(
    certfile=svid.cert_chain_pem,
    keyfile=svid.private_key_pem
)
context.load_verify_locations(svid.bundle.pem)
```

---

## 5. Troubleshooting

### 5.1: SPIRE Server Won't Start

**Symptoms:** Container exits immediately

**Check:**
```bash
docker compose logs spire-server

# Common issues:
# 1. Missing upstream CA
ls -la spire/server/dummy_upstream_ca.*

# 2. Permission issues
chmod 600 spire/server/dummy_upstream_ca.key

# 3. Config syntax error
docker run --rm -v $(pwd)/spire/server:/conf \
    ghcr.io/spiffe/spire-server:1.9.0 \
    -config /conf/server.conf -validate
```

### 5.2: SPIRE Agent Can't Connect to Server

**Symptoms:** Agent unhealthy, can't attest workloads

**Check:**
```bash
# Verify server is healthy first
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server healthcheck

# Check agent logs
docker compose logs spire-agent | grep -i error

# Common issues:
# 1. Join token expired (TTL 1 hour by default)
./spire/init-spire.sh bootstrap  # Regenerate

# 2. Network connectivity
docker exec gitlab-sre-spire-agent ping spire-server
```

### 5.3: Workload Can't Fetch SVID

**Symptoms:** Application can't get certificates

**Check:**
```bash
# Verify entry exists
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry show | grep my-service

# Verify labels match
docker inspect <container_name> | jq '.[0].Config.Labels'

# Check agent logs for attestation
docker compose logs spire-agent | grep -i attest
```

### 5.4: SVID Expired / Not Rotating

**Symptoms:** mTLS connections failing after ~1 hour

**Check:**
```bash
# Verify agent is running
docker exec gitlab-sre-spire-agent /opt/spire/bin/spire-agent healthcheck

# Check SVID expiry
openssl x509 -in /path/to/svid.pem -noout -dates

# Restart agent to force refresh
docker restart gitlab-sre-spire-agent
```

---

## 6. Monitoring

### 6.1: Health Checks

```bash
# Cron job / monitoring script
#!/bin/bash
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server healthcheck || \
    curl -X POST https://alerts.example.com/spire-server-unhealthy

docker exec gitlab-sre-spire-agent /opt/spire/bin/spire-agent healthcheck || \
    curl -X POST https://alerts.example.com/spire-agent-unhealthy
```

### 6.2: Prometheus Metrics

SPIRE exposes metrics on the health check port:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'spire-server'
    static_configs:
      - targets: ['spire-server:8080']
    metrics_path: '/metrics'
```

### 6.3: Key Metrics to Watch

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `spire_server_svid_issued_total` | SVIDs issued | Trend |
| `spire_agent_svid_expiry_seconds` | Time until SVID expires | < 600 |
| `spire_server_entries_total` | Registered entries | Change detection |

---

## 7. Backup & Recovery

### 7.1: Backup SPIRE Data

```bash
# Backup server data (includes entries database)
docker cp gitlab-sre-spire-server:/opt/spire/data/server ./spire-server-backup-$(date +%Y%m%d)

# Backup upstream CA (CRITICAL - store securely!)
cp spire/server/dummy_upstream_ca.* /secure/backup/
```

### 7.2: Restore SPIRE

```bash
# Stop services
docker compose down spire-server spire-agent

# Restore data
docker cp ./spire-server-backup-YYYYMMDD/. gitlab-sre-spire-server:/opt/spire/data/server

# Start services
docker compose up -d spire-server spire-agent
```

### 7.3: CA Rotation (Annual)

```bash
# Generate new CA
openssl req -x509 -newkey rsa:4096 \
    -keyout spire/server/new_upstream_ca.key \
    -out spire/server/new_upstream_ca.crt \
    -days 365 -nodes \
    -subj "/C=US/O=Ravenhelm/CN=Ravenhelm Root CA"

# Update server.conf to point to new CA
# Restart SPIRE server
# Old SVIDs will continue working until they expire
# New SVIDs will be signed by new CA
```

---

## 8. Security Checklist

### Initial Setup
- [ ] Upstream CA generated with strong key (4096-bit RSA)
- [ ] CA private key secured (chmod 600, limited access)
- [ ] SPIRE server healthy
- [ ] SPIRE agent healthy
- [ ] All workloads registered

### Ongoing
- [ ] SVID TTL appropriate for environment
- [ ] CA rotation scheduled (annual)
- [ ] Monitoring alerts configured
- [ ] Backup procedure tested
- [ ] Access to SPIRE server API restricted

### Production Hardening
- [ ] Use hardware-backed key storage (HSM/TPM)
- [ ] Enable audit logging
- [ ] Use upstream CA from real PKI (not self-signed)
- [ ] Implement node attestation (not just join token)
- [ ] Restrict workload API socket access

---

## Quick Reference

### Commands

```bash
# 1. Generate upstream CA (one-time)
./spire/init-spire.sh ca

# 2. Start SPIRE server
docker compose up -d spire-server
# Wait for healthy
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server healthcheck

# 3. Generate join token
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server token generate \
    -spiffeID spiffe://ravenhelm.local/agent/local -ttl 3600
# Copy the token value

# 4. Start SPIRE agent with token
SPIRE_JOIN_TOKEN="<token>" docker compose up -d spire-agent
# Or save token to .env file and run: docker compose up -d spire-agent

# Health checks
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server healthcheck
docker exec gitlab-sre-spire-agent /opt/spire/bin/spire-agent healthcheck

# List entries
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry show

# Register new workload
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry create \
    -parentID spiffe://ravenhelm.local/agent/local \
    -spiffeID spiffe://ravenhelm.local/workload/<name> \
    -selector docker:label:ravenhelm.workload:<name>
```

### Files

| File | Purpose |
|------|---------|
| `spire/server/server.conf` | SPIRE server configuration |
| `spire/agent/agent.conf` | SPIRE agent configuration |
| `spire/server/dummy_upstream_ca.crt` | Root CA certificate |
| `spire/server/dummy_upstream_ca.key` | Root CA private key (PROTECT!) |
| `spire/init-spire.sh` | Bootstrap script |

### SPIFFE IDs

| Service | SPIFFE ID |
|---------|-----------|
| Agent | `spiffe://ravenhelm.local/agent/local` |
| PostgreSQL | `spiffe://ravenhelm.local/workload/postgres` |
| Redis | `spiffe://ravenhelm.local/workload/redis` |
| NATS | `spiffe://ravenhelm.local/workload/nats` |
| Grafana | `spiffe://ravenhelm.local/workload/grafana` |
| Hliðskjálf | `spiffe://ravenhelm.local/workload/control-plane` |
| Norns | `spiffe://ravenhelm.local/workload/norns` |

---

*"Trust nothing. Verify everything."*

