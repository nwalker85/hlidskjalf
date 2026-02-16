# RUNBOOK-026: External Model Server mTLS Setup

**Status**: Active  
**Category**: Security, Zero-Trust, External Services  
**Last Updated**: 2025-12-06

---

## Purpose

Configure mTLS authentication for the external model server at `models.ravenhelm` (192.168.50.26:6701) using SPIRE/SPIFFE for zero-trust communication.

---

## Prerequisites

- SPIRE server running on the Hliðskjálf platform (`gitlab-sre-spire-server`)
- Traefik configured with SPIRE SVIDs (`ravenhelm-proxy`)
- Access to the external model server (192.168.50.26)

---

## Architecture Options

### Option A: Full SPIRE mTLS (Recommended)

Both Traefik and the model server use SPIRE SVIDs for mutual authentication.

```
[Client] --HTTPS--> [Traefik:443] --mTLS(SPIRE)--> [Model Server:6701]
                    (SVID Client)                    (SVID Server)
```

**Advantages:**
- True mutual authentication
- Auto-rotating certificates (via SPIRE)
- Full zero-trust compliance
- No static credentials

**Requirements:**
- SPIRE agent running on 192.168.50.26
- Model service configured to use SVID certificates

### Option B: Traefik Client Certificate

Traefik presents its SVID as a client certificate; model server validates.

```
[Client] --HTTPS--> [Traefik:443] --HTTPS+ClientCert--> [Model Server:6701]
                    (SVID as client cert)                (Validates Traefik cert)
```

**Advantages:**
- Simpler setup (no SPIRE agent on remote machine)
- Still leverages SPIRE for Traefik's identity
- Model server can be any HTTPS service

**Requirements:**
- Model server configured for HTTPS with client cert validation
- Trust anchor (SPIRE bundle) installed on model server

---

## Option A: Full SPIRE Setup

### Step 1: Install SPIRE Agent on Model Server

On `192.168.50.26`:

```bash
# Download SPIRE
curl -L https://github.com/spiffe/spire/releases/download/v1.9.0/spire-1.9.0-linux-amd64-musl.tar.gz -o spire.tar.gz
tar -xzf spire.tar.gz
sudo mv spire-1.9.0/bin/* /usr/local/bin/
sudo mkdir -p /opt/spire/{conf,data}

# Create agent configuration
sudo tee /opt/spire/conf/agent.conf << 'EOF'
agent {
    data_dir = "/opt/spire/data"
    log_level = "INFO"
    server_address = "10.10.0.10"  # Hliðskjálf SPIRE server IP
    server_port = "8081"
    socket_path = "/run/spire/sockets/api.sock"
    trust_domain = "ravenhelm.local"
}

plugins {
    NodeAttestor "join_token" {
        plugin_data {}
    }
    
    KeyManager "disk" {
        plugin_data {
            directory = "/opt/spire/data"
        }
    }
    
    WorkloadAttestor "unix" {
        plugin_data {}
    }
}
EOF
```

### Step 2: Generate Join Token and Start Agent

On the Hliðskjálf platform:

```bash
# Generate join token for external agent
JOIN_TOKEN=$(docker exec gitlab-sre-spire-server \
    /opt/spire/bin/spire-server token generate \
    -spiffeID spiffe://ravenhelm.local/agent/model-server \
    -ttl 600 | grep Token: | awk '{print $2}')

echo "Join Token: $JOIN_TOKEN"
```

On `192.168.50.26`:

```bash
# Start the agent with join token
sudo /usr/local/bin/spire-agent run \
    -config /opt/spire/conf/agent.conf \
    -joinToken "$JOIN_TOKEN" &

# Or create systemd service
sudo tee /etc/systemd/system/spire-agent.service << 'EOF'
[Unit]
Description=SPIRE Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/spire-agent run -config /opt/spire/conf/agent.conf
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable spire-agent
sudo systemctl start spire-agent
```

### Step 3: Register Model Server Workload

On the Hliðskjálf platform:

```bash
# Register the model server workload
docker exec gitlab-sre-spire-server \
    /opt/spire/bin/spire-server entry create \
    -spiffeID spiffe://ravenhelm.local/workload/model-server \
    -parentID spiffe://ravenhelm.local/agent/model-server \
    -selector unix:uid:1001 \
    -ttl 3600

# Verify registration
docker exec gitlab-sre-spire-server \
    /opt/spire/bin/spire-server entry show \
    -spiffeID spiffe://ravenhelm.local/workload/model-server
```

### Step 4: Configure Model Service with SVID

On `192.168.50.26`, configure your model service (e.g., Ollama, vLLM) to use SPIRE certificates:

```bash
# Install spiffe-helper
curl -L https://github.com/spiffe/spiffe-helper/releases/download/v0.6.0/spiffe-helper_0.6.0_linux_amd64.tar.gz -o helper.tar.gz
tar -xzf helper.tar.gz
sudo mv spiffe-helper /usr/local/bin/

# Create spiffe-helper config
sudo tee /etc/spiffe-helper.conf << 'EOF'
agent_address = "/run/spire/sockets/api.sock"
cmd = ""
cmd_args = ""
cert_dir = "/run/spire/certs"
svid_file_name = "svid.pem"
svid_key_file_name = "key.pem"
svid_bundle_file_name = "bundle.pem"
renew_signal = ""
add_intermediates_to_bundle = true
EOF

# Start spiffe-helper
sudo /usr/local/bin/spiffe-helper -config /etc/spiffe-helper.conf &
```

**Configure your model service to use the certificates:**

For Ollama with HTTPS:
```bash
export OLLAMA_HOST=https://0.0.0.0:6701
export OLLAMA_CERT_FILE=/run/spire/certs/svid.pem
export OLLAMA_KEY_FILE=/run/spire/certs/key.pem
```

For other services, update their TLS configuration to point to:
- Certificate: `/run/spire/certs/svid.pem`
- Key: `/run/spire/certs/key.pem`
- CA Bundle: `/run/spire/certs/bundle.pem`

### Step 5: Update Traefik Configuration

Already configured in `ravenhelm-proxy/dynamic.yml`:

```yaml
http:
  serversTransports:
    model-server-transport:
      rootCAs:
        - /certs/spire-bundle.pem
      certificates:
        - certFile: /run/spire/certs/svid.pem
          keyFile: /run/spire/certs/key.pem

  routers:
    model-server:
      rule: "Host(`models.ravenhelm.dev`)"
      service: model-server-svc
      middlewares:
        - secure-headers
      tls:
        certResolver: letsencrypt

  services:
    model-server-svc:
      loadBalancer:
        serversTransport: model-server-transport
        servers:
          - url: "https://192.168.50.26:6701"  # Note: HTTPS now
```

### Step 6: Test Connection

```bash
# From any container with Traefik access
curl -H "Host: models.ravenhelm.dev" https://localhost/v1/models

# Or from host with proper DNS
curl https://models.ravenhelm.dev/v1/models
```

---

## Option B: Traefik Client Certificate (Simpler)

### Step 1: Export SPIRE Bundle to Model Server

On the Hliðskjálf platform:

```bash
# Export SPIRE bundle
docker exec gitlab-sre-spire-server \
    /opt/spire/bin/spire-server bundle show \
    -format pem > /tmp/spire-bundle.pem

# Copy to model server
scp /tmp/spire-bundle.pem user@192.168.50.26:/etc/ssl/certs/spire-ca.pem
```

### Step 2: Configure Model Server to Validate Client Certs

On `192.168.50.26`, configure your model service to require and validate client certificates using the SPIRE bundle as the CA.

**Example for Nginx reverse proxy in front of Ollama:**

```nginx
server {
    listen 6701 ssl;
    server_name models.ravenhelm;

    # Server certificate (can be self-signed or LE)
    ssl_certificate /etc/ssl/certs/model-server.crt;
    ssl_certificate_key /etc/ssl/private/model-server.key;

    # Require client certificate
    ssl_verify_client on;
    ssl_client_certificate /etc/ssl/certs/spire-ca.pem;
    ssl_verify_depth 2;

    location / {
        proxy_pass http://127.0.0.1:11434;  # Local Ollama
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-SSL-Client-Cert $ssl_client_cert;
    }
}
```

**Or for Caddy:**

```caddyfile
models.ravenhelm:6701 {
    tls /etc/ssl/certs/model-server.crt /etc/ssl/private/model-server.key {
        client_auth {
            mode require_and_verify
            trusted_ca_cert_file /etc/ssl/certs/spire-ca.pem
        }
    }
    
    reverse_proxy localhost:11434
}
```

### Step 3: Update Traefik Configuration

Same as Option A - Traefik will present its SVID as the client certificate.

---

## Verification

### Check SPIRE Registration

```bash
# List all entries
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry show

# Check model server specifically
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry show \
    -spiffeID spiffe://ravenhelm.local/workload/model-server
```

### Test mTLS Connection

```bash
# From Traefik container
docker exec ravenhelm-proxy curl -v https://192.168.50.26:6701/health

# Check certificate details
openssl s_client -connect 192.168.50.26:6701 \
    -cert /run/spire/certs/svid.pem \
    -key /run/spire/certs/key.pem \
    -CAfile /run/spire/certs/bundle.pem
```

### Monitor Certificate Rotation

```bash
# Watch SVID on model server
watch -n 5 'openssl x509 -in /run/spire/certs/svid.pem -noout -dates'
```

---

## Troubleshooting

### Agent Won't Connect

```bash
# Check SPIRE server is reachable from external machine
telnet 10.10.0.10 8081

# Check agent logs
journalctl -u spire-agent -f

# Verify trust domain matches
grep trust_domain /opt/spire/conf/agent.conf
```

### SVID Not Issued

```bash
# Check agent health
/usr/local/bin/spire-agent healthcheck -socketPath /run/spire/sockets/api.sock

# Fetch workload API
/usr/local/bin/spire-agent api fetch x509 -socketPath /run/spire/sockets/api.sock
```

### Traefik Can't Connect

```bash
# Verify serversTransport is applied
docker exec ravenhelm-proxy cat /dynamic.yml | grep -A 10 model-server-transport

# Check Traefik logs
docker logs ravenhelm-proxy -f | grep model-server
```

---

## Security Considerations

1. **Network Segmentation**: Ensure 192.168.50.26 is on a trusted network segment
2. **Firewall Rules**: Restrict port 6701 to only allow Traefik's IP
3. **Workload Attestation**: Use appropriate selectors (unix:uid, docker:label, etc.)
4. **Certificate Rotation**: SPIRE auto-rotates; ensure services reload certs
5. **Audit Logging**: Monitor SPIRE entry creation/deletion

---

## Related Runbooks

- [RUNBOOK-004: SPIRE Management](./RUNBOOK-004-spire-management.md)
- [RUNBOOK-024: Add Shared Service](./RUNBOOK-024-add-shared-service.md)
- [RUNBOOK-005: File Ownership & Permissions](./RUNBOOK-005-file-ownership-permissions.md)

---

## Maintenance

- **Certificate TTL**: Default 1 hour, rotates at 50%
- **Agent Health**: Monitor via `spire-agent healthcheck`
- **Entry Audit**: Periodically review with `entry show`
- **Bundle Rotation**: SPIRE handles automatically


