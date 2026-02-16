# Hliðskjálf Platform Reorganization

## Current Reality vs Target Structure

### SSH Key Routing (from `~/.ssh/config`)
```
github.com-quant   → ~/.ssh/quant_ed25519      (Quant/ projects)
github.com-nwalker → ~/.ssh/github_ed25519    (nwalker85/ projects)
```

### Target Folder Structure

```
~/Development/
├── hlidskjalf/                    # ← MOVE gitlab-sre HERE
│   │                              #   Neutral ground - serves all realms
│   ├── docker-compose.yml         # Main platform orchestration
│   ├── README.md
│   │
│   ├── ravenhelm-proxy/           # Central reverse proxy (*.ravenhelm.test)
│   │   ├── nginx.conf
│   │   ├── docker-compose.yml
│   │   └── config/certs/
│   │
│   ├── observability/             # The Eye of Odin
│   │   ├── grafana/
│   │   ├── prometheus/
│   │   ├── loki/
│   │   ├── tempo/
│   │   ├── otel-collector/
│   │   └── alertmanager/
│   │
│   ├── postgres/                  # Shared PostgreSQL (pgvector)
│   │   └── init/
│   │
│   ├── spire/                     # Zero-trust identity
│   │   ├── server/
│   │   └── agent/
│   │
│   ├── localstack/                # AWS emulation
│   ├── openbao/                   # Secrets management
│   ├── redpanda/                  # Kafka-compatible events
│   │
│   ├── hlidskjalf/                # The Dashboard (API + UI)
│   │   ├── src/                   # FastAPI backend
│   │   │   └── norns/             # AI assistant
│   │   └── ui/                    # Next.js frontend
│   │
│   ├── templates/                 # Project boilerplates
│   │   └── ravenmaskos/           # FastAPI + Next.js template
│   │
│   └── tests/                     # Platform-wide testing
│       └── saaa-tests/
│
├── nwalker85/                     # Personal Projects (github.com-nwalker)
│   ├── Jarvis/                    # Personal assistant v1
│   ├── myjarvis/                  # Personal assistant v2 (voice)
│   └── [future personal projects]
│
└── Quant/                         # Work Projects (github.com-quant)
    ├── agentswarm/                # Agent Crucible - voice AI platform
    ├── CIBC/                      # Client documentation
    └── Projects/
        ├── agentfoundry/          # Agent builder platform
        ├── myTinyCRM/             # CRM demo
        ├── livekit-dual-agent/    # Voice agent testing
        ├── m2c-demo/              # M2C demo app
        ├── JiraInterpreter/       # Jira integration
        ├── n8n/                   # n8n fork/customization
        └── serviceasanagent/      # Service wrapper patterns
```

---

## Project Inventory

### Shared Platform Services (hlidskjalf/)

| Service | Domain | Internal Port | Purpose |
|---------|--------|---------------|---------|
| ravenhelm-proxy | *.ravenhelm.test | 80/443 | SSL termination, routing |
| postgres | - | 5432 | Shared database (pgvector) |
| redis | - | 6379 | Cache, sessions |
| localstack | localstack.ravenhelm.test | 4566 | AWS emulation |
| redpanda | events.ravenhelm.test | 9092/8081 | Kafka-compatible streaming |
| nats | - | 4222 | Low-latency messaging |
| openbao | vault.ravenhelm.test | 8200 | Secrets management |
| spire-server | - | 8081 | SPIFFE identity |
| otel-collector | - | 4317/4318 | Telemetry ingestion |
| prometheus | prometheus.observe.ravenhelm.test | 9090 | Metrics |
| loki | loki.observe.ravenhelm.test | 3100 | Logs |
| tempo | tempo.observe.ravenhelm.test | 3200 | Traces |
| grafana | grafana.observe.ravenhelm.test | 3000 | Dashboards |
| alertmanager | alertmanager.observe.ravenhelm.test | 9093 | Alerts |
| langfuse | langfuse.observe.ravenhelm.test | 3001 | LLM observability |
| phoenix | phoenix.observe.ravenhelm.test | 6006 | Embeddings debug |
| hlidskjalf-api | hlidskjalf-api.ravenhelm.test | 8000 | Platform API |
| hlidskjalf-ui | hlidskjalf.ravenhelm.test | 3002 | Platform Dashboard |

### Personal Projects (nwalker85/)

| Project | Domain | API Port | UI Port | Status |
|---------|--------|----------|---------|--------|
| Jarvis | jarvis.ravenhelm.test | 8101 | 3101 | Active |
| myjarvis | myjarvis.ravenhelm.test | 8102 | 3102 | Active |

### Work Projects (Quant/)

| Project | Domain | API Port | UI Port | Status |
|---------|--------|----------|---------|--------|
| agentswarm | saaa.ravenhelm.test | 8201 | 3201 | Active |
| agentfoundry | foundry.ravenhelm.test | 8202 | 3202 | Active |
| myTinyCRM | tinycrm.ravenhelm.test | 8203 | 3203 | Active |
| livekit-dual-agent | livekit.ravenhelm.test | 8204 | 3204 | Testing |
| m2c-demo | m2c.ravenhelm.test | 8205 | 3205 | Demo |
| JiraInterpreter | jira.ravenhelm.test | 8206 | 3206 | Dev |

---

## Port Allocation Strategy

### Reserved Ranges

```
0-1023      : System (avoid)
1024-4999   : Platform infrastructure
5000-7999   : Shared services
8000-8099   : Hlidskjalf platform
8100-8199   : Personal projects (nwalker85/)
8200-8299   : Work projects (Quant/)
8300-8399   : Sandbox/testing
9000-9999   : Monitoring/metrics

3000-3099   : Platform UIs
3100-3199   : Personal project UIs
3200-3299   : Work project UIs
3300-3399   : Sandbox UIs
```

### Fixed Platform Ports (Never Auto-Assign)

```yaml
# Infrastructure
postgres:        5432
redis:           6379
nats:            4222
localstack:      4566
openbao:         8200
redpanda_kafka:  9092
redpanda_schema: 8081
redpanda_admin:  9644

# Observability
grafana:         3000
prometheus:      9090
alertmanager:    9093
loki:            3100
tempo:           3200
otel_grpc:       4317
otel_http:       4318
langfuse:        3001
phoenix:         6006

# Platform
hlidskjalf_api:  8000
hlidskjalf_ui:   3002

# Voice/Realtime
livekit:         7880
livekit_turn:    3478
```

### Port Registry & Checks

- `config/port_registry.yaml` is the authoritative ledger for project paths, port ranges, and next-available slots.
- `scripts/port_checks/<project>.sh` validates that a project's API/UI ports and satellite services stay inside their assigned ranges:

```bash
./scripts/port_checks/agentswarm.sh
```

Run these before adding a new domain or when troubleshooting conflicts—if a script fails, the registry needs an update before any compose/k8s manifests change.

### Subnet Guidance

Port ranges already partition the cognitive fabric logically. Subnets become useful when the stack leaves a single Docker host (Tailnet peers, VLANs, or multi-node Kubernetes). Map each range onto a /28 or /24 slice (e.g., `10.10.0.0/24` for platform, `10.10.10.0/24` for personal, `10.10.20.0/24` for work) whenever you need deterministic routing or firewall policy. For pure local development the default docker bridge is fine—treat subnetting as a hardening/scale lever, not a prerequisite.

---

## Migration Commands

```bash
# 1. Move gitlab-sre to top level as hlidskjalf
mv ~/Development/Quant/Projects/gitlab-sre ~/Development/hlidskjalf

# 2. Update git remote (if needed - this is platform infrastructure)
cd ~/Development/hlidskjalf
# Consider: this repo could use either SSH key or be a platform-level repo

# 3. Reorganize templates
mkdir -p ~/Development/hlidskjalf/templates
mv ~/Development/hlidskjalf/ravenmaskos ~/Development/hlidskjalf/templates/

# 4. Reorganize tests
mkdir -p ~/Development/hlidskjalf/tests
mv ~/Development/hlidskjalf/saaa-tests ~/Development/hlidskjalf/tests/

# 5. Update DNS entries in /etc/hosts (if not using dnsmasq)
# Or configure dnsmasq to resolve *.ravenhelm.test → 127.0.0.1
```

---

## DNS Configuration

### Option A: /etc/hosts (Manual)
Add entries for each service manually.

### Option B: dnsmasq (Recommended)
```bash
# Install dnsmasq
brew install dnsmasq

# Configure wildcard
echo "address=/ravenhelm.test/127.0.0.1" >> /opt/homebrew/etc/dnsmasq.conf

# Create resolver
sudo mkdir -p /etc/resolver
echo "nameserver 127.0.0.1" | sudo tee /etc/resolver/ravenhelm.test

# Start dnsmasq
brew services start dnsmasq
```

This gives you `*.ravenhelm.test` → `127.0.0.1` automatically.

### Certificate Management (mkcert)

Use mkcert to keep every `*.ravenhelm.test` service on a single, trusted wildcard certificate:

```bash
brew install mkcert nss      # once per machine
mkcert -install              # trusts the Ravenhelm Dev CA

cd ravenhelm-proxy/config/certs
mkcert -cert-file server.crt -key-file server.key \
  ravenhelm.test \
  "*.ravenhelm.test" \
  "*.observe.ravenhelm.test" \
  "*.events.ravenhelm.test" \
  vault.ravenhelm.test \
  localstack.ravenhelm.test \
  "*.saaa.ravenhelm.test" \
  "*.agentcrucible.ravenhelm.test"

cp server.crt server.key ../../config/certs/
```

Repeat the `mkcert` command any time you introduce new realms/domains so the SAN list stays current. Mkcert writes the CA to the macOS System keychain automatically, so browsers trust the cert without manual Keychain steps.

