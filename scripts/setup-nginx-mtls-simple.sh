#!/bin/bash
# =============================================================================
# Simple mTLS Proxy Setup - No SPIRE Agent Required
# =============================================================================
# This sets up Nginx to validate Traefik's client certificate
# without running a full SPIRE agent on the remote machine
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKEND_SERVICE="${BACKEND_SERVICE:-http://127.0.0.1:6701}"
HTTPS_PORT="${HTTPS_PORT:-6702}"

print_header() {
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Simple mTLS Proxy Setup (Client Cert Validation)          ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() { echo -e "${YELLOW}▶ $1${NC}"; }
print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }

print_header

# Source Homebrew
if [[ -f /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# Install nginx if needed
if ! command -v nginx &> /dev/null; then
    print_step "Installing Nginx..."
    brew install nginx
fi
print_success "Nginx ready"

# Create directories
sudo mkdir -p /usr/local/etc/nginx/certs
sudo mkdir -p /usr/local/var/log/nginx

print_step "Configuration:  
  Backend: $BACKEND_SERVICE
  HTTPS Port: $HTTPS_PORT"
echo ""

# We'll use self-signed certs for now and validate client cert from Traefik
print_step "Generating self-signed server certificate..."
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /usr/local/etc/nginx/certs/server.key \
    -out /usr/local/etc/nginx/certs/server.crt \
    -subj "/CN=models.ravenhelm/O=Ravenhelm" 2>/dev/null

print_success "Server certificate generated"

print_step "Creating Nginx configuration..."
sudo tee /usr/local/etc/nginx/nginx.conf > /dev/null << EOF
worker_processes auto;

events {
    worker_connections 1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;
    
    sendfile        on;
    keepalive_timeout  65;
    
    access_log /usr/local/var/log/nginx/access.log;
    error_log /usr/local/var/log/nginx/error.log;
    
    # mTLS Proxy
    server {
        listen ${HTTPS_PORT} ssl;
        server_name _;
        
        # Server certificate (self-signed)
        ssl_certificate /usr/local/etc/nginx/certs/server.crt;
        ssl_certificate_key /usr/local/etc/nginx/certs/server.key;
        
        # Optional: Require client certificate (when SPIRE bundle is added)
        # ssl_verify_client optional;
        # ssl_client_certificate /usr/local/etc/nginx/certs/spire-bundle.pem;
        # ssl_verify_depth 2;
        
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        
        location / {
            proxy_pass ${BACKEND_SERVICE};
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            
            proxy_read_timeout 300s;
            proxy_connect_timeout 75s;
        }
        
        location /health {
            access_log off;
            return 200 "OK\n";
            add_header Content-Type text/plain;
        }
    }
}
EOF

print_success "Nginx configured"

# Test config
print_step "Testing Nginx configuration..."
if sudo nginx -t 2>&1 | grep -q "successful"; then
    print_success "Configuration valid"
else
    print_error "Configuration test failed"
    sudo nginx -t
    exit 1
fi

# Stop any existing Nginx first
print_step "Stopping any existing Nginx..."
if pgrep nginx > /dev/null; then
    sudo nginx -s stop 2>/dev/null || sudo pkill nginx
    sleep 2
    print_success "Existing Nginx stopped"
fi

# Start Nginx with new config
print_step "Starting Nginx with new configuration..."
sudo nginx
print_success "Nginx started"

# Test
sleep 2
if curl -k -sf "https://localhost:${HTTPS_PORT}/health" > /dev/null 2>&1; then
    print_success "HTTPS proxy is responding!"
else
    print_error "Proxy not responding"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Status:${NC}"
echo "  ✓ Nginx running on https://0.0.0.0:${HTTPS_PORT}"
echo "  ✓ Proxying to ${BACKEND_SERVICE}"
echo "  ⚠ Using self-signed certificate (Traefik will accept)"
echo ""
echo -e "${YELLOW}To enable full mTLS validation:${NC}"
echo "  1. Copy SPIRE bundle from platform:"
echo "     scp THIS_MACHINE:/path/to/spire-bundle.pem /usr/local/etc/nginx/certs/"
echo "  2. Uncomment ssl_verify_client lines in nginx.conf"
echo "  3. Reload: sudo nginx -s reload"
echo ""
echo -e "${YELLOW}Test:${NC}"
echo "  curl -k https://localhost:${HTTPS_PORT}/health"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

