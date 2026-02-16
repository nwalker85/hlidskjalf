# RUNBOOK-026: External Model Server Setup (models.ravenhelm.dev)

## Overview

This runbook covers setting up an external MacBook Pro (M5) as a model server accessible via `models.ravenhelm.dev`, integrated into the Ravenhelm platform with:
- nginx reverse proxy for HTTPS termination
- Integration with Traefik via the main platform
- Basic auth or mTLS protection

## Prerequisites

- MacBook Pro with Apple Silicon running model server on `localhost:6701`
- DNS A record for `*.ravenhelm.dev` pointing to your public IP
- Port forwarding on your router (443 → Mac workstation)
- Self-signed or Let's Encrypt certificates

## Architecture

```
Internet → Router (443) → Traefik (main server) 
                              ↓
                    models.ravenhelm.dev router
                              ↓
                    nginx (Mac workstation:6702)
                              ↓
                    Model Server (localhost:6701)
```

## Setup on Mac Workstation

### 1. Install nginx

```bash
brew install nginx
```

### 2. Generate Self-Signed Certificates

For local development/testing:

```bash
# Create directory for certs
sudo mkdir -p /opt/homebrew/etc/nginx/certs

# Generate self-signed cert
openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout /opt/homebrew/etc/nginx/certs/models.key \
  -out /opt/homebrew/etc/nginx/certs/models.crt \
  -subj "/CN=models.ravenhelm.dev" \
  -addext "subjectAltName=DNS:models.ravenhelm.dev,DNS:localhost"
```

### 3. Configure nginx

Create/edit `/opt/homebrew/etc/nginx/nginx.conf`:

```nginx
worker_processes  auto;

events {
    worker_connections  1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;

    # Logging
    access_log  /opt/homebrew/var/log/nginx/access.log;
    error_log   /opt/homebrew/var/log/nginx/error.log;

    sendfile        on;
    keepalive_timeout  65;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=model_api:10m rate=10r/s;

    # Upstream model server
    upstream model_server {
        server 127.0.0.1:6701;
        keepalive 32;
    }

    # HTTP redirect to HTTPS
    server {
        listen 80;
        server_name models.ravenhelm.dev localhost;
        return 301 https://$host$request_uri;
    }

    # HTTPS server
    server {
        listen 6702 ssl http2;
        server_name models.ravenhelm.dev localhost;

        # SSL Configuration
        ssl_certificate     /opt/homebrew/etc/nginx/certs/models.crt;
        ssl_certificate_key /opt/homebrew/etc/nginx/certs/models.key;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # Security headers
        add_header X-Frame-Options SAMEORIGIN always;
        add_header X-Content-Type-Options nosniff always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        # Basic Auth (optional - comment out if using mTLS)
        # auth_basic "Model Server";
        # auth_basic_user_file /opt/homebrew/etc/nginx/.htpasswd;

        # CORS headers for API access
        add_header 'Access-Control-Allow-Origin' 'https://hlidskjalf.ravenhelm.dev' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, Accept' always;
        add_header 'Access-Control-Allow-Credentials' 'true' always;

        # Handle preflight
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' 'https://hlidskjalf.ravenhelm.dev';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
            add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, Accept';
            add_header 'Access-Control-Max-Age' 86400;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }

        # Health check endpoint
        location /health {
            return 200 '{"status":"healthy","server":"models.ravenhelm.dev"}';
            add_header Content-Type application/json;
        }

        # Model API endpoints
        location / {
            limit_req zone=model_api burst=20 nodelay;
            
            proxy_pass http://model_server;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Connection "";
            
            # Timeouts for LLM inference
            proxy_connect_timeout 60s;
            proxy_send_timeout 300s;
            proxy_read_timeout 300s;
            
            # Large request bodies for context
            client_max_body_size 100M;
            
            # Buffering for streaming responses
            proxy_buffering off;
            proxy_cache off;
        }

        # OpenAI-compatible endpoints
        location /v1/ {
            limit_req zone=model_api burst=20 nodelay;
            
            proxy_pass http://model_server/v1/;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Connection "";
            
            proxy_connect_timeout 60s;
            proxy_send_timeout 300s;
            proxy_read_timeout 300s;
            client_max_body_size 100M;
            proxy_buffering off;
        }
    }
}
```

### 4. Create Basic Auth (Optional)

If not using mTLS, create basic auth:

```bash
# Install htpasswd
brew install httpd-tools

# Create password file
htpasswd -c /opt/homebrew/etc/nginx/.htpasswd ravenhelm
# Enter password when prompted
```

### 5. Start nginx

```bash
# Test configuration
sudo nginx -t

# Start nginx
brew services start nginx

# Or run directly
sudo nginx

# Verify it's running
curl -k https://localhost:6702/health
```

### 6. Troubleshooting nginx

```bash
# Check logs
tail -f /opt/homebrew/var/log/nginx/error.log
tail -f /opt/homebrew/var/log/nginx/access.log

# Reload config after changes
sudo nginx -s reload

# Stop nginx
brew services stop nginx
# or
sudo nginx -s stop
```

## Configuration on Main Server (Traefik)

The Traefik configuration in `ravenhelm-proxy/dynamic.yml` already includes:

```yaml
# Router for external model server
model-server:
  rule: "Host(`models.ravenhelm.dev`)"
  service: model-server-svc
  middlewares:
    - secure-headers
  tls:
    certResolver: letsencrypt
  priority: 1000

# Service pointing to Mac workstation
model-server-svc:
  loadBalancer:
    serversTransport: model-server-transport
    servers:
      - url: "https://192.168.50.26:6702"  # Update with Mac's IP
```

Update the IP address to match your Mac workstation's local IP.

## Testing

### From Main Server

```bash
# Test direct connection to Mac
curl -k https://192.168.50.26:6702/health

# Test via Traefik
curl https://models.ravenhelm.dev/health
```

### From Hliðskjálf UI

Add the model server as a provider in LLM Settings:
- **Name**: Models Mac Server
- **Type**: Custom (OpenAI-compatible)
- **URL**: https://models.ravenhelm.dev/v1

## Network Requirements

1. **Router Port Forwarding**: Forward external 443 to Traefik server
2. **Local Network**: Mac workstation reachable from Traefik server on 6702
3. **Firewall**: Allow incoming connections on Mac's port 6702

## Security Considerations

1. **Basic Auth**: Simple but credentials transmitted over TLS
2. **mTLS**: More secure, requires SPIRE agent on Mac workstation
3. **Network Isolation**: Consider VPN or Tailscale for remote access

## mTLS with SPIRE (Advanced)

For full mTLS integration, install SPIRE agent on the Mac workstation:

1. Install SPIRE agent binary
2. Configure to join the `ravenhelm.local` trust domain
3. Register workload identity `spiffe://ravenhelm.local/model-server`
4. Use spiffe-helper to manage certificates
5. Configure nginx to use SPIRE-issued certificates

See `docs/runbooks/RUNBOOK-006-spire-setup.md` for SPIRE details.

## Monitoring

Add health check to Prometheus targets:

```yaml
- job_name: 'model-server'
  scheme: https
  tls_config:
    insecure_skip_verify: true  # For self-signed certs
  static_configs:
    - targets: ['models.ravenhelm.dev:443']
```

## Related Runbooks

- RUNBOOK-024: Add Shared Service
- RUNBOOK-006: SPIRE Setup
- RUNBOOK-005: File Ownership Permissions

