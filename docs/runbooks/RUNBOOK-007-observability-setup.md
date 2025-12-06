# RUNBOOK-007: Observability Stack Setup

## Overview

This runbook documents the first-time setup of the Hliðskjálf observability stack, which provides centralized logging, metrics, and tracing through Grafana.

**Components:**
- **Grafana Alloy** - Unified collection agent (logs, metrics, traces)
- **Loki** - Log aggregation and storage
- **Prometheus** - Metrics storage and alerting
- **Tempo** - Distributed tracing
- **Grafana** - Visualization and dashboards

## Prerequisites

- Docker and Docker Compose installed
- Hliðskjálf platform cloned and configured
- dnsmasq configured for `*.ravenhelm.test` domains
- Traefik running as the ingress proxy

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Docker Containers                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                │
│  │ Service │ │ Service │ │ Service │ │ Service │                │
│  │    A    │ │    B    │ │    C    │ │    D    │                │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘                │
│       │           │           │           │                      │
│       └───────────┴─────┬─────┴───────────┘                      │
│                         │                                        │
│                         ▼                                        │
│                 ┌───────────────┐                                │
│                 │ Grafana Alloy │                                │
│                 │  (collector)  │                                │
│                 └───────┬───────┘                                │
│                         │                                        │
│         ┌───────────────┼───────────────┐                       │
│         ▼               ▼               ▼                        │
│    ┌─────────┐    ┌──────────┐    ┌─────────┐                   │
│    │  Loki   │    │Prometheus│    │  Tempo  │                   │
│    │ (logs)  │    │(metrics) │    │(traces) │                   │
│    └────┬────┘    └────┬─────┘    └────┬────┘                   │
│         └───────────────┼───────────────┘                       │
│                         ▼                                        │
│                 ┌───────────────┐                                │
│                 │    Grafana    │                                │
│                 │ (dashboards)  │                                │
│                 └───────────────┘                                │
└──────────────────────────────────────────────────────────────────┘
```

## First-Time Setup

### Step 1: Verify Required Services

Ensure these services are defined in `docker-compose.yml`:

```bash
grep -E "^\s+(loki|prometheus|tempo|grafana|alloy):" docker-compose.yml
```

Expected output:
```
  loki:
  prometheus:
  tempo:
  grafana:
  alloy:
```

### Step 2: Create Configuration Directories

```bash
mkdir -p observability/alloy
mkdir -p observability/loki
mkdir -p observability/prometheus
mkdir -p observability/tempo
mkdir -p observability/grafana/provisioning/dashboards/json
mkdir -p observability/grafana/provisioning/datasources
```

### Step 3: Configure Grafana Alloy

Create `observability/alloy/config.alloy`:

```alloy
// =============================================================================
// Grafana Alloy Configuration
// =============================================================================
// Unified observability collector for:
// - Docker container logs → Loki
// - Application metrics → Prometheus
// - Traces → Tempo (via OTLP)
// =============================================================================

logging {
  level  = "info"
  format = "logfmt"
}

// -----------------------------------------------------------------------------
// LOGGING: Docker Container Logs → Loki
// -----------------------------------------------------------------------------

// Discover running Docker containers
discovery.docker "containers" {
  host = "unix:///var/run/docker.sock"
  
  filter {
    name   = "status"
    values = ["running"]
  }
}

// Collect logs from discovered containers
loki.source.docker "docker_logs" {
  host       = "unix:///var/run/docker.sock"
  targets    = discovery.docker.containers.targets
  forward_to = [loki.process.docker_logs.receiver]
  
  relabel_rules = loki.relabel.docker_labels.rules
}

// Relabel rules for Docker labels → Loki labels
loki.relabel "docker_labels" {
  forward_to = []

  // Container name (strip leading /)
  rule {
    source_labels = ["__meta_docker_container_name"]
    regex         = "/(.*)"
    target_label  = "container"
  }

  // Docker Compose service name
  rule {
    source_labels = ["__meta_docker_container_label_com_docker_compose_service"]
    target_label  = "service"
  }

  // Docker Compose project
  rule {
    source_labels = ["__meta_docker_container_label_com_docker_compose_project"]
    target_label  = "project"
  }

  // Container ID
  rule {
    source_labels = ["__meta_docker_container_id"]
    target_label  = "container_id"
  }

  // Job label (same as service)
  rule {
    source_labels = ["__meta_docker_container_label_com_docker_compose_service"]
    target_label  = "job"
  }
}

// Process logs - Docker stage handles JSON/logfmt/plain text
loki.process "docker_logs" {
  forward_to = [loki.write.loki.receiver]

  stage.docker {}
  
  // Extract log level from common patterns
  stage.regex {
    expression = "(?i)(level=|\\s)(debug|info|warn|warning|error|fatal|panic|critical)\\b"
  }
}

// Write to Loki
loki.write "loki" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}

// -----------------------------------------------------------------------------
// METRICS: Prometheus scraping
// -----------------------------------------------------------------------------

// Scrape Alloy's own metrics
prometheus.scrape "alloy_self" {
  targets = [{
    __address__ = "127.0.0.1:12345",
  }]
  forward_to = [prometheus.remote_write.prometheus.receiver]
  job_name   = "alloy"
}

// Remote write to Prometheus
prometheus.remote_write "prometheus" {
  endpoint {
    url = "http://prometheus:9090/api/v1/write"
  }
}

// -----------------------------------------------------------------------------
// TRACING: OTLP receiver → Tempo
// -----------------------------------------------------------------------------

// Receive OTLP traces from applications
otelcol.receiver.otlp "default" {
  grpc {
    endpoint = "0.0.0.0:4317"
  }
  http {
    endpoint = "0.0.0.0:4318"
  }
  output {
    traces = [otelcol.exporter.otlp.tempo.input]
  }
}

// Export to Tempo
otelcol.exporter.otlp "tempo" {
  client {
    endpoint = "tempo:4317"
    tls {
      insecure = true
    }
  }
}

// -----------------------------------------------------------------------------
// LOGGING: Application OTLP logs → Loki
// -----------------------------------------------------------------------------

otelcol.receiver.otlp "logs" {
  grpc {
    endpoint = "0.0.0.0:4319"
  }
  output {
    logs = [otelcol.exporter.loki.default.input]
  }
}

otelcol.exporter.loki "default" {
  forward_to = [loki.write.loki.receiver]
}
```

### Step 4: Configure Grafana Datasources

Create `observability/grafana/provisioning/datasources/datasources.yml`:

> **CRITICAL:** Always specify explicit `uid` values! Dashboards reference datasources by UID, and Grafana auto-generates random UIDs if not specified, causing "datasource not found" errors.

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    uid: prometheus  # REQUIRED: Must match dashboard JSON references
    isDefault: true
    editable: false

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    uid: loki  # REQUIRED: Must match dashboard JSON references
    editable: false

  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200
    uid: tempo  # REQUIRED: Must match dashboard JSON references
    editable: false
    jsonData:
      httpMethod: GET
      nodeGraph:
        enabled: true
```

### Step 5: Configure Dashboard Provisioning

Create `observability/grafana/provisioning/dashboards/default.yml`:

```yaml
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: 'Platform'
    folderUid: 'platform'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards/json
```

### Step 6: Docker Compose Configuration

Ensure `docker-compose.yml` includes:

```yaml
services:
  alloy:
    image: grafana/alloy:latest
    container_name: ${COMPOSE_PROJECT_NAME:-hlidskjalf}-alloy
    restart: unless-stopped
    command:
      - run
      - --server.http.listen-addr=0.0.0.0:12345
      - /etc/alloy/config.alloy
    volumes:
      - ./observability/alloy/config.alloy:/etc/alloy/config.alloy:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - alloy_data:/var/lib/alloy
    ports:
      - "4317:4317"   # OTLP gRPC (traces)
      - "4318:4318"   # OTLP HTTP (traces)
      - "4319:4319"   # OTLP gRPC (logs)
      - "12345:12345" # Alloy UI
    networks:
      - hlidskjalf
    depends_on:
      - loki
      - prometheus
      - tempo

  loki:
    image: grafana/loki:latest
    container_name: ${COMPOSE_PROJECT_NAME:-hlidskjalf}-loki
    restart: unless-stopped
    ports:
      - "3100:3100"
    volumes:
      - ./observability/loki/loki-config.yml:/etc/loki/local-config.yaml:ro
      - loki_data:/loki
    networks:
      - hlidskjalf

  prometheus:
    image: prom/prometheus:latest
    container_name: ${COMPOSE_PROJECT_NAME:-hlidskjalf}-prometheus
    restart: unless-stopped
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.enable-remote-write-receiver'
    ports:
      - "9090:9090"
    volumes:
      - ./observability/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    networks:
      - hlidskjalf

  tempo:
    image: grafana/tempo:latest
    container_name: ${COMPOSE_PROJECT_NAME:-hlidskjalf}-tempo
    restart: unless-stopped
    command: ["-config.file=/etc/tempo/tempo.yaml"]
    ports:
      - "3200:3200"   # Tempo HTTP
      - "14268:14268" # Jaeger ingest
    volumes:
      - ./observability/tempo/tempo.yaml:/etc/tempo/tempo.yaml:ro
      - tempo_data:/tmp/tempo
    networks:
      - hlidskjalf

  grafana:
    image: grafana/grafana:latest
    container_name: ${COMPOSE_PROJECT_NAME:-hlidskjalf}-grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - ./observability/grafana/provisioning:/etc/grafana/provisioning:ro
      - grafana_data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
      - GF_USERS_ALLOW_SIGN_UP=false
    networks:
      - hlidskjalf
    depends_on:
      - loki
      - prometheus
      - tempo

volumes:
  alloy_data:
  loki_data:
  prometheus_data:
  tempo_data:
  grafana_data:
```

### Step 6a: Alerting Rules

1. Reference the rules directory from `observability/prometheus/prometheus.yml`:

   ```yaml
   rule_files:
     - "rules/self_heal.rules.yml"
   ```

2. Maintain the baseline alerts in `/Users/nwalker/Development/hlidskjalf/observability/prometheus/rules/self_heal.rules.yml`. This file ships the platform-wide `ServiceDown`, `HighErrorRate`, `HighLatency`, `HighCPU`, `HighMemory`, and `ContainerRestarting` alerts used by Alertmanager.
3. After editing any rule files, reload Prometheus with `curl -X POST http://localhost:9090/-/reload` (requires `--web.enable-lifecycle`) or `docker compose restart prometheus`.

### Step 7: Start the Observability Stack

```bash
# Start services in order
docker compose up -d loki prometheus tempo
sleep 5
docker compose up -d alloy grafana
```

### Step 8: Verify Services

```bash
# Check all services are healthy
docker compose ps | grep -E "loki|prometheus|tempo|alloy|grafana"

# Check Alloy is discovering containers
docker compose logs alloy 2>&1 | tail -20

# Verify Loki is receiving logs
curl -s "http://localhost:3100/loki/api/v1/labels" | jq .
```

## Accessing Dashboards

| Service | URL |
|---------|-----|
| Grafana | https://grafana.observe.ravenhelm.test |
| Alloy UI | https://alloy.observe.ravenhelm.test |
| Prometheus | https://prometheus.observe.ravenhelm.test |
| Loki | https://loki.observe.ravenhelm.test |

## Troubleshooting

### No Logs Appearing in Loki

1. **Check Alloy is discovering containers:**
   ```bash
   curl -s http://localhost:12345/api/v0/targets | jq '.[] | select(.type=="loki.source.docker")'
   ```

2. **Enable debug logging temporarily:**
   Edit `config.alloy`:
   ```alloy
   logging {
     level  = "debug"
     format = "logfmt"
   }
   ```
   Then restart: `docker compose restart alloy`

3. **Reset Alloy state if containers were recreated:**
   ```bash
   docker compose stop alloy
   docker volume rm hlidskjalf_alloy_data
   docker compose up -d alloy
   ```

### Port Already Allocated

```bash
# Find what's using the port
lsof -i :4317

# If it's an old OTEL collector
docker compose stop otel-collector
```

### Grafana Dashboards Not Showing

```bash
# Force dashboard reload
docker compose restart grafana

# Check provisioning errors
docker compose logs grafana 2>&1 | grep -i "provisioning\|dashboard"
```

## Adding Application Tracing

For Python applications using OpenTelemetry:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Configure exporter to send to Alloy
exporter = OTLPSpanExporter(endpoint="http://alloy:4317", insecure=True)

# Set up tracer
provider = TracerProvider()
processor = BatchSpanProcessor(exporter)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Use in code
tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("my-operation"):
    # Your code here
    pass
```

## Maintenance

### Log Retention

Configure Loki retention in `observability/loki/loki-config.yml`:

```yaml
limits_config:
  retention_period: 168h  # 7 days
```

### Disk Usage

Monitor volume sizes:

```bash
docker system df -v | grep -E "loki|prometheus|tempo|alloy|grafana"
```

## References

- [Grafana Alloy Documentation](https://grafana.com/docs/alloy/latest/)
- [Loki LogQL](https://grafana.com/docs/loki/latest/query/)
- [Prometheus PromQL](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- `docs/LESSONS_LEARNED.md` - Platform troubleshooting insights

