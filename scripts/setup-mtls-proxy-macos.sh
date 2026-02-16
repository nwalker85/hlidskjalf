#!/bin/bash
# =============================================================================
# Setup mTLS Proxy for Existing HTTP Service - macOS Apple Silicon
# =============================================================================
# This script sets up an Nginx reverse proxy with SPIRE mTLS validation
# in front of an existing HTTP service. Your service keeps running as-is.
#
# Usage:
#   ./setup-mtls-proxy-macos.sh
#
# Prerequisites:
#   - macOS with Apple Silicon
#   - Existing HTTP service running (e.g., on port 11434)
#   - Network connectivity to SPIRE server
#   - sudo access
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SPIRE_VERSION="1.13.3"
SPIFFE_HELPER_VERSION="0.6.0"
SPIRE_SERVER_IP="${SPIRE_SERVER_IP:-10.10.0.10}"
SPIRE_SERVER_PORT="${SPIRE_SERVER_PORT:-8081}"
TRUST_DOMAIN="ravenhelm.local"
SOCKET_PATH="/tmp/spire-agent/public/api.sock"
CERT_DIR="/tmp/spire-certs"

# Service configuration
BACKEND_SERVICE="${BACKEND_SERVICE:-http://127.0.0.1:11434}"
HTTPS_PORT="${HTTPS_PORT:-6701}"

# Functions
print_header() {
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   mTLS Proxy Setup - macOS Apple Silicon                    ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

check_prerequisites() {
    print_step "Checking prerequisites..."
    
    if [[ "$(uname -s)" != "Darwin" ]]; then
        print_error "This script is for macOS only"
        exit 1
    fi
    
    if [[ "$(uname -m)" != "arm64" ]]; then
        print_error "This script is for Apple Silicon (ARM64) only"
        exit 1
    fi
    
    print_success "macOS Apple Silicon detected"
    
    if ! sudo -v; then
        print_error "sudo access required"
        exit 1
    fi
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        # Try Apple Silicon path
        if [[ -f "/opt/homebrew/bin/brew" ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        else
            print_error "Homebrew not installed. Install from https://brew.sh"
            echo "Or run: ./scripts/install-homebrew-remote.sh"
            exit 1
        fi
    fi
    
    print_success "Prerequisites checked"
    echo ""
}

install_nginx() {
    print_step "Installing Nginx..."
    
    if command -v nginx &> /dev/null; then
        print_success "Nginx already installed: $(nginx -v 2>&1)"
    else
        brew install nginx
        print_success "Nginx installed"
    fi
    echo ""
}

install_spire() {
    print_step "Installing SPIRE agent..."
    
    if command -v spire-agent &> /dev/null; then
        print_success "SPIRE agent already installed: $(spire-agent --version | head -1)"
        return
    fi
    
    # Install SPIRE via Homebrew (build from source)
    print_step "Installing SPIRE from source via Homebrew..."
    print_step "This may take 5-10 minutes..."
    
    # Add spiffe tap
    brew tap spiffe/spiffe || true
    
    # Install spire (this builds from source)
    if brew install spire 2>&1 | tee /tmp/spire-install.log; then
        print_success "SPIRE installed via Homebrew"
    else
        print_error "Homebrew install failed, trying manual Go install..."
        
        # Fallback: Install Go and build from source
        if ! command -v go &> /dev/null; then
            print_step "Installing Go..."
            brew install go
        fi
        
        print_step "Building SPIRE from source..."
        cd /tmp
        if [[ ! -d "spire-${SPIRE_VERSION}-src" ]]; then
            curl -L "https://github.com/spiffe/spire/archive/refs/tags/v${SPIRE_VERSION}.tar.gz" -o spire-src.tar.gz
            tar -xzf spire-src.tar.gz
            mv "spire-${SPIRE_VERSION}" "spire-${SPIRE_VERSION}-src"
        fi
        
        cd "spire-${SPIRE_VERSION}-src"
        make build
        sudo cp bin/spire-agent /usr/local/bin/
        sudo cp bin/spire-server /usr/local/bin/
    fi
    
    if command -v spire-agent &> /dev/null; then
        print_success "SPIRE agent installed"
    else
        print_error "SPIRE agent installation failed"
        exit 1
    fi
    
    echo ""
}

install_spiffe_helper() {
    print_step "Installing spiffe-helper..."
    
    cd /tmp
    
    if command -v spiffe-helper &> /dev/null; then
        print_success "spiffe-helper already installed"
        return
    fi
    
    # Try darwin-arm64 first
    local helper_url="https://github.com/spiffe/spiffe-helper/releases/download/v${SPIFFE_HELPER_VERSION}/spiffe-helper_${SPIFFE_HELPER_VERSION}_darwin_arm64.tar.gz"
    
    if [[ ! -f "spiffe-helper_${SPIFFE_HELPER_VERSION}_darwin_arm64.tar.gz" ]]; then
        if curl -fL -o "spiffe-helper_${SPIFFE_HELPER_VERSION}_darwin_arm64.tar.gz" "$helper_url" 2>/dev/null; then
            tar -xzf "spiffe-helper_${SPIFFE_HELPER_VERSION}_darwin_arm64.tar.gz"
            sudo mv spiffe-helper /usr/local/bin/ 2>/dev/null || true
        else
            # Fallback to Linux ARM64
            print_step "Darwin binary not available, using Linux ARM64..."
            helper_url="https://github.com/spiffe/spiffe-helper/releases/download/v${SPIFFE_HELPER_VERSION}/spiffe-helper_${SPIFFE_HELPER_VERSION}_linux_arm64.tar.gz"
            curl -fL -o "spiffe-helper_${SPIFFE_HELPER_VERSION}_linux_arm64.tar.gz" "$helper_url"
            tar -xzf "spiffe-helper_${SPIFFE_HELPER_VERSION}_linux_arm64.tar.gz"
            sudo mv spiffe-helper /usr/local/bin/ 2>/dev/null || true
        fi
    fi
    
    if command -v spiffe-helper &> /dev/null; then
        print_success "spiffe-helper installed"
    else
        print_error "spiffe-helper installation failed"
        exit 1
    fi
    
    echo ""
}

create_spire_configs() {
    print_step "Creating SPIRE configurations..."
    
    sudo mkdir -p /opt/spire/{conf,data}
    sudo mkdir -p "$(dirname "$SOCKET_PATH")"
    sudo mkdir -p "$CERT_DIR"
    
    # SPIRE agent config
    sudo tee /opt/spire/conf/agent.conf > /dev/null << EOF
agent {
    data_dir = "/opt/spire/data"
    log_level = "INFO"
    server_address = "$SPIRE_SERVER_IP"
    server_port = "$SPIRE_SERVER_PORT"
    socket_path = "$SOCKET_PATH"
    trust_domain = "$TRUST_DOMAIN"
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
    
    # spiffe-helper config
    sudo tee /etc/spiffe-helper.conf > /dev/null << EOF
agent_address = "$SOCKET_PATH"
cert_dir = "$CERT_DIR"
svid_file_name = "svid.pem"
svid_key_file_name = "key.pem"
svid_bundle_file_name = "bundle.pem"
add_intermediates_to_bundle = true
EOF
    
    print_success "SPIRE configs created"
    echo ""
}

create_nginx_config() {
    print_step "Creating Nginx mTLS proxy configuration..."
    
    # Backup existing config if present
    if [[ -f /usr/local/etc/nginx/nginx.conf ]]; then
        sudo cp /usr/local/etc/nginx/nginx.conf /usr/local/etc/nginx/nginx.conf.backup
    fi
    
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
    
    # Logging
    access_log /usr/local/var/log/nginx/access.log;
    error_log /usr/local/var/log/nginx/error.log;
    
    # mTLS Proxy for Model Server
    server {
        listen ${HTTPS_PORT} ssl;
        server_name _;
        
        # Server certificate (SPIRE SVID)
        ssl_certificate ${CERT_DIR}/svid.pem;
        ssl_certificate_key ${CERT_DIR}/key.pem;
        
        # Require client certificate (from Traefik)
        ssl_verify_client on;
        ssl_client_certificate ${CERT_DIR}/bundle.pem;
        ssl_verify_depth 2;
        
        # SSL settings
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;
        
        # Proxy to backend HTTP service
        location / {
            proxy_pass ${BACKEND_SERVICE};
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            
            # Pass client cert info to backend
            proxy_set_header X-Client-Cert-Verified \$ssl_client_verify;
            proxy_set_header X-Client-Cert-Subject \$ssl_client_s_dn;
            
            # Timeouts for LLM requests
            proxy_read_timeout 300s;
            proxy_connect_timeout 75s;
        }
        
        # Health check endpoint
        location /health {
            access_log off;
            return 200 "OK\n";
            add_header Content-Type text/plain;
        }
    }
}
EOF
    
    print_success "Nginx config created at /usr/local/etc/nginx/nginx.conf"
    echo ""
}

create_launchd_services() {
    print_step "Creating launchd services..."
    
    # SPIRE Agent
    sudo tee /Library/LaunchDaemons/com.spiffe.agent.plist > /dev/null << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.spiffe.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/spire-agent</string>
        <string>run</string>
        <string>-config</string>
        <string>/opt/spire/conf/agent.conf</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/spire-agent.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/spire-agent-error.log</string>
</dict>
</plist>
EOF
    
    # spiffe-helper
    sudo tee /Library/LaunchDaemons/com.spiffe.helper.plist > /dev/null << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.spiffe.helper</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/spiffe-helper</string>
        <string>-config</string>
        <string>/etc/spiffe-helper.conf</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/spiffe-helper.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/spiffe-helper-error.log</string>
</dict>
</plist>
EOF
    
    print_success "launchd services created"
    echo ""
}

get_join_token() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}Join Token Required${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "You need a join token from the Hliðskjálf platform."
    echo ""
    echo "On the Hliðskjálf machine, run:"
    echo -e "${GREEN}  ./scripts/register-model-server-spire.sh --generate-token${NC}"
    echo ""
    echo -n "Enter join token: "
    read -r JOIN_TOKEN
    
    if [[ -z "$JOIN_TOKEN" ]]; then
        print_error "Join token required"
        return 1
    fi
    
    return 0
}

start_services() {
    local token="$1"
    
    print_step "Starting SPIRE agent..."
    
    # Start agent with join token
    sudo /usr/local/bin/spire-agent run \
        -config /opt/spire/conf/agent.conf \
        -joinToken "$token" > /var/log/spire-agent.log 2>&1 &
    
    # Wait for socket
    local attempts=0
    while [[ ! -S "$SOCKET_PATH" ]] && [[ $attempts -lt 30 ]]; do
        sleep 1
        ((attempts++))
    done
    
    if [[ ! -S "$SOCKET_PATH" ]]; then
        print_error "SPIRE agent socket not created"
        return 1
    fi
    
    print_success "SPIRE agent running"
    
    # Start spiffe-helper
    print_step "Starting spiffe-helper..."
    sudo launchctl load /Library/LaunchDaemons/com.spiffe.helper.plist 2>/dev/null || true
    
    # Wait for certificates
    sleep 5
    
    if [[ -f "$CERT_DIR/svid.pem" ]]; then
        print_success "Certificates generated"
    else
        print_error "Certificates not generated yet"
        return 1
    fi
    
    # Start Nginx
    print_step "Starting Nginx..."
    
    # Test config
    if ! sudo nginx -t 2>/dev/null; then
        print_error "Nginx config test failed"
        sudo nginx -t
        return 1
    fi
    
    # Start or reload
    if pgrep nginx > /dev/null; then
        sudo nginx -s reload
        print_success "Nginx reloaded"
    else
        sudo nginx
        print_success "Nginx started"
    fi
    
    echo ""
}

verify_setup() {
    print_step "Verifying setup..."
    
    # Check backend service
    if curl -sf "$BACKEND_SERVICE" > /dev/null 2>&1; then
        print_success "Backend service is responding"
    else
        print_error "Backend service not responding at $BACKEND_SERVICE"
    fi
    
    # Check HTTPS endpoint
    sleep 2
    if curl -k -sf "https://localhost:${HTTPS_PORT}/health" > /dev/null 2>&1; then
        print_success "mTLS proxy is responding on port ${HTTPS_PORT}"
    else
        print_error "mTLS proxy not responding"
    fi
    
    echo ""
}

print_next_steps() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}Setup Complete!${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}Your existing service at ${BACKEND_SERVICE}${NC}"
    echo -e "${YELLOW}is now protected with mTLS on https://0.0.0.0:${HTTPS_PORT}${NC}"
    echo ""
    echo -e "${YELLOW}Architecture:${NC}"
    echo "  [Traefik] --mTLS--> [Nginx:${HTTPS_PORT}] --HTTP--> [Your Service]"
    echo ""
    echo -e "${YELLOW}Test locally:${NC}"
    echo -e "  ${GREEN}curl -k https://localhost:${HTTPS_PORT}/health${NC}"
    echo ""
    echo -e "${YELLOW}View logs:${NC}"
    echo -e "  ${GREEN}tail -f /var/log/spire-agent.log${NC}"
    echo -e "  ${GREEN}tail -f /usr/local/var/log/nginx/access.log${NC}"
    echo -e "  ${GREEN}tail -f /usr/local/var/log/nginx/error.log${NC}"
    echo ""
    echo -e "${YELLOW}Manage services:${NC}"
    echo -e "  ${GREEN}sudo nginx -s stop${NC}"
    echo -e "  ${GREEN}sudo nginx -s reload${NC}"
    echo -e "  ${GREEN}sudo launchctl stop com.spiffe.agent${NC}"
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
}

# Main
main() {
    print_header
    
    # Get configuration
    echo -e "${YELLOW}Configuration:${NC}"
    echo -n "Backend service URL [${BACKEND_SERVICE}]: "
    read -r user_backend
    BACKEND_SERVICE="${user_backend:-$BACKEND_SERVICE}"
    
    echo -n "HTTPS port [${HTTPS_PORT}]: "
    read -r user_port
    HTTPS_PORT="${user_port:-$HTTPS_PORT}"
    
    echo ""
    
    check_prerequisites
    install_nginx
    install_spire
    install_spiffe_helper
    create_spire_configs
    create_nginx_config
    create_launchd_services
    
    if get_join_token; then
        if start_services "$JOIN_TOKEN"; then
            verify_setup
            print_next_steps
        fi
    fi
}

main "$@"

