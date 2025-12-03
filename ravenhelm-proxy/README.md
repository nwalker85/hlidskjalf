# Ravenhelm Proxy

Central reverse proxy for all `*.ravenhelm.test` projects. Provides unified SSL termination and routes traffic to project-specific nginx instances.

## Architecture

```
Browser (HTTPS :443)
    ↓
ravenhelm-proxy (:443)
    ├── *.saaa.ravenhelm.test        → localhost:8443  (SAAA project)
    ├── *.agentcrucible.ravenhelm.test → localhost:9443  (Agent Crucible)
    └── *.{newproject}.ravenhelm.test  → localhost:{port} (Future projects)
    ↓
Project nginx (internal SSL)
    ↓
Internal services
```

## Quick Start

```bash
# Start the proxy
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f nginx

# Restart after config changes
docker compose restart nginx
```

## Project Routing

| Project | Domain Pattern | Internal Port |
|---------|---------------|---------------|
| SAAA | `*.saaa.ravenhelm.test` | 8443 |
| Agent Crucible | `*.agentcrucible.ravenhelm.test` | 9443 |

## Adding a New Project

### 1. Choose a unique port (e.g., 10443)

### 2. Add server block to `nginx.conf`:

```nginx
# =========================================================================
# YOUR PROJECT - *.yourproject.ravenhelm.test -> localhost:{port}
# =========================================================================
server {
    listen 443 ssl;
    server_name yourproject.ravenhelm.test *.yourproject.ravenhelm.test;

    location / {
        proxy_pass https://host.docker.internal:{port};
        proxy_http_version 1.1;
        proxy_ssl_verify off;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_buffering off;
    }
}
```

### 3. Update certificate SANs (if needed)

If your domains aren't covered by `*.ravenhelm.test`, add them to the certificate. See **Certificate Management** below.

### 4. Restart the proxy

```bash
docker compose restart nginx
```

### 5. Configure your project's nginx

Your project should have its own nginx listening on `{port}` (e.g., 10443) with SSL enabled.

## Port Mappings

| Port | Protocol | Purpose |
|------|----------|---------|
| 443 | HTTPS | Main entry point for all `*.ravenhelm.test` |
| 7885 | TCP | LiveKit WebSocket signaling (SAAA) |
| 7886 | TCP | LiveKit TCP fallback (SAAA) |
| 7887-7897 | UDP | LiveKit WebRTC media (SAAA) |

## DNS Configuration

DNS is handled by dnsmasq running locally:

- **Config**: `/opt/homebrew/etc/dnsmasq.conf`
- **Port**: 15353
- **Resolver**: `/etc/resolver/ravenhelm.test`

All `*.ravenhelm.test` domains resolve to `127.0.0.1`.

```bash
# Check DNS resolution
dig frontend.saaa.ravenhelm.test @127.0.0.1 -p 15353 +short
# Should return: 127.0.0.1

# Check dnsmasq is running
brew services list | grep dnsmasq
```

## Certificate Management

Certificates are stored in `config/certs/` and shared across all projects.

| File | Purpose |
|------|---------|
| `ca.crt` | Ravenhelm Development CA |
| `ca.key` | CA private key |
| `server.crt` | Wildcard server certificate |
| `server.key` | Server private key |

### Generate Certificates with mkcert (Recommended)

```bash
brew install mkcert nss    # once per machine
mkcert -install            # trusts the Ravenhelm Dev CA

cd config/certs
mkcert -cert-file server.crt -key-file server.key \
  ravenhelm.test \
  "*.ravenhelm.test" \
  "*.observe.ravenhelm.test" \
  "*.events.ravenhelm.test" \
  vault.ravenhelm.test \
  localstack.ravenhelm.test \
  "*.saaa.ravenhelm.test" \
  "*.agentcrucible.ravenhelm.test"

# share with other stacks that mount ../../config/certs
cp server.crt server.key ../../config/certs/
```

Re-run the `mkcert` command whenever new domains are introduced so their SANs are added automatically. Mkcert writes the CA to the macOS System keychain as part of `mkcert -install`, so browsers trust the cert immediately.

### Certificate Requirements

The server certificate must have:
- `keyUsage = digitalSignature, keyEncipherment`
- `extendedKeyUsage = serverAuth`
- SANs for all required domains

### Current SANs

```
DNS:ravenhelm.test
DNS:*.ravenhelm.test
DNS:saaa.ravenhelm.test
DNS:*.saaa.ravenhelm.test
DNS:agentcrucible.ravenhelm.test
DNS:*.agentcrucible.ravenhelm.test
```

### Manual OpenSSL Regeneration (Fallback)

If mkcert is unavailable you can still mint a cert from the Ravenhelm CA:

```bash
cd config/certs

cat > server.ext << 'EOF'
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = ravenhelm.test
DNS.2 = *.ravenhelm.test
DNS.3 = saaa.ravenhelm.test
DNS.4 = *.saaa.ravenhelm.test
DNS.5 = agentcrucible.ravenhelm.test
DNS.6 = *.agentcrucible.ravenhelm.test
DNS.7 = yourproject.ravenhelm.test
DNS.8 = *.yourproject.ravenhelm.test
EOF

openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr \
    -subj "/C=US/ST=Development/L=Local/O=Ravenhelm/OU=Development/CN=*.ravenhelm.test"
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out server.crt -days 365 -sha256 -extfile server.ext

# Clean up
rm server.csr server.ext

# Copy to project(s) that need it
cp server.crt server.key /path/to/project/config/certs/

# Restart all nginx containers
docker compose restart nginx
# Also restart project nginx containers
```

### Trusting the CA (macOS)

The CA must be trusted in macOS Keychain for browsers to accept the certificates:

```bash
# Add to System Keychain and trust
sudo security add-trusted-cert -d -r trustRoot \
    -k /Library/Keychains/System.keychain config/certs/ca.crt

# Verify trust settings
security dump-trust-settings -d | grep -A10 "Ravenhelm"
```

If the command-line trust doesn't work (common on newer macOS):
1. Open **Keychain Access**
2. Go to **System** keychain
3. Find **Ravenhelm Development CA**
4. Double-click → expand **Trust** → set to **Always Trust**

## Troubleshooting

### Check nginx status
```bash
docker compose ps
docker compose logs nginx --tail 20
```

### Test configuration
```bash
docker compose exec nginx nginx -t
```

### Test endpoints
```bash
# Quick health check
curl -sk https://frontend.saaa.ravenhelm.test/ -o /dev/null -w "%{http_code}"

# With verbose SSL info
curl -svk https://frontend.saaa.ravenhelm.test/ 2>&1 | grep -E "SSL|subject|issuer"
```

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `502 Bad Gateway` | Project nginx not running | Start project's docker compose |
| `Connection refused` | Wrong port mapping | Check project listens on correct port |
| `ERR_SSL_KEY_USAGE_INCOMPATIBLE` | Missing `digitalSignature` in cert | Regenerate certificate |
| `NET::ERR_CERT_AUTHORITY_INVALID` | CA not trusted | Trust CA in Keychain |
| DNS not resolving | dnsmasq not running | `brew services start dnsmasq` |

### Reload without restart
```bash
docker compose exec nginx nginx -s reload
```

## Docker Desktop Watcher

A utility script that monitors Docker Desktop and automatically restarts it if it stops running.

### Usage

```bash
# Run in foreground
./docker-watcher.sh

# Run in background
./docker-watcher.sh &

# With custom settings
POLL_INTERVAL=5 MAX_WAIT=120 ./docker-watcher.sh
```

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `POLL_INTERVAL` | 10 | Seconds between status checks |
| `MAX_WAIT` | 60 | Max seconds to wait for Docker to start |

### Running as a Background Service

```bash
# Start in background with nohup (persists after terminal closes)
nohup ./docker-watcher.sh > docker-watcher.log 2>&1 &

# Check if running
pgrep -f docker-watcher

# Stop the watcher
pkill -f docker-watcher
```

### Running via launchd (Recommended for persistent monitoring)

Create `~/Library/LaunchAgents/com.ravenhelm.docker-watcher.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ravenhelm.docker-watcher</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/nwalker/Development/Quant/Projects/ravenhelm-proxy/docker-watcher.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/docker-watcher.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/docker-watcher.log</string>
</dict>
</plist>
```

```bash
# Load the service
launchctl load ~/Library/LaunchAgents/com.ravenhelm.docker-watcher.plist

# Unload the service
launchctl unload ~/Library/LaunchAgents/com.ravenhelm.docker-watcher.plist

# Check status
launchctl list | grep docker-watcher
```

## File Structure

```
ravenhelm-proxy/
├── README.md
├── docker-compose.yml
├── docker-watcher.sh
├── nginx.conf
└── config/
    └── certs/
        ├── ca.crt
        ├── ca.key
        ├── server.crt
        └── server.key
```

## Related Projects

- **SAAA**: `/Users/nwalker/Development/Quant/Projects/serviceasanagent`
- **Agent Crucible**: (path TBD)

## Related System Files

- `/etc/resolver/ravenhelm.test` - macOS resolver config
- `/opt/homebrew/etc/dnsmasq.conf` - dnsmasq configuration
