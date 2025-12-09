#!/bin/bash
# =============================================================================
# Setup External Model Server with SPIRE mTLS - macOS Apple Silicon
# =============================================================================
# This script automates the setup of SPIRE agent and spiffe-helper on
# macOS with Apple Silicon (M1/M2/M3/M4/M5) for mTLS authentication.
#
# Usage:
#   # Generate join token first on Hliðskjálf platform:
#   ./scripts/register-model-server-spire.sh --generate-token
#
#   # Then run this script on the external macOS machine:
#   ./setup-model-server-macos.sh
#
# Prerequisites:
#   - macOS with Apple Silicon
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
SPIRE_VERSION="1.9.0"
SPIFFE_HELPER_VERSION="0.6.0"
SPIRE_SERVER_IP="${SPIRE_SERVER_IP:-10.10.0.10}"
SPIRE_SERVER_PORT="${SPIRE_SERVER_PORT:-8081}"
TRUST_DOMAIN="ravenhelm.local"
SOCKET_PATH="/tmp/spire-agent/public/api.sock"
CERT_DIR="/tmp/spire-certs"

# Functions
print_header() {
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   External Model Server Setup - macOS Apple Silicon         ║${NC}"
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
    
    # Check if running on macOS
    if [[ "$(uname -s)" != "Darwin" ]]; then
        print_error "This script is for macOS only"
        exit 1
    fi
    
    # Check if Apple Silicon
    if [[ "$(uname -m)" != "arm64" ]]; then
        print_error "This script is for Apple Silicon (ARM64) only"
        echo "Detected architecture: $(uname -m)"
        exit 1
    fi
    
    print_success "macOS Apple Silicon detected"
    
    # Check sudo access
    if ! sudo -v; then
        print_error "sudo access required"
        exit 1
    fi
    
    print_success "Prerequisites checked"
    echo ""
}

download_spire() {
    print_step "Downloading SPIRE agent (darwin-arm64)..."
    
    cd /tmp
    
    if [[ -f "spire-${SPIRE_VERSION}-darwin-arm64.tar.gz" ]]; then
        print_success "SPIRE tarball already exists, skipping download"
    else
        curl -L -o "spire-${SPIRE_VERSION}-darwin-arm64.tar.gz" \
            "https://github.com/spiffe/spire/releases/download/v${SPIRE_VERSION}/spire-${SPIRE_VERSION}-darwin-arm64.tar.gz"
        print_success "Downloaded SPIRE agent"
    fi
    
    # Extract and install
    tar -xzf "spire-${SPIRE_VERSION}-darwin-arm64.tar.gz"
    sudo mv "spire-${SPIRE_VERSION}/bin/"* /usr/local/bin/ 2>/dev/null || true
    
    # Verify
    if command -v spire-agent &> /dev/null; then
        print_success "SPIRE agent installed: $(spire-agent --version | head -1)"
    else
        print_error "SPIRE agent installation failed"
        exit 1
    fi
    
    echo ""
}

download_spiffe_helper() {
    print_step "Downloading spiffe-helper (darwin-arm64)..."
    
    cd /tmp
    
    if [[ -f "spiffe-helper_${SPIFFE_HELPER_VERSION}_darwin_arm64.tar.gz" ]]; then
        print_success "spiffe-helper tarball already exists, skipping download"
    else
        curl -L -o "spiffe-helper_${SPIFFE_HELPER_VERSION}_darwin_arm64.tar.gz" \
            "https://github.com/spiffe/spiffe-helper/releases/download/v${SPIFFE_HELPER_VERSION}/spiffe-helper_${SPIFFE_HELPER_VERSION}_darwin_arm64.tar.gz"
        print_success "Downloaded spiffe-helper"
    fi
    
    # Extract and install
    tar -xzf "spiffe-helper_${SPIFFE_HELPER_VERSION}_darwin_arm64.tar.gz"
    sudo mv spiffe-helper /usr/local/bin/ 2>/dev/null || true
    
    # Verify
    if command -v spiffe-helper &> /dev/null; then
        print_success "spiffe-helper installed"
    else
        print_error "spiffe-helper installation failed"
        exit 1
    fi
    
    echo ""
}

create_spire_config() {
    print_step "Creating SPIRE agent configuration..."
    
    sudo mkdir -p /opt/spire/{conf,data}
    sudo mkdir -p "$(dirname "$SOCKET_PATH")"
    
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
    
    print_success "SPIRE agent config created at /opt/spire/conf/agent.conf"
    echo ""
}

create_spiffe_helper_config() {
    print_step "Creating spiffe-helper configuration..."
    
    sudo mkdir -p "$CERT_DIR"
    
    sudo tee /etc/spiffe-helper.conf > /dev/null << EOF
agent_address = "$SOCKET_PATH"
cert_dir = "$CERT_DIR"
svid_file_name = "svid.pem"
svid_key_file_name = "key.pem"
svid_bundle_file_name = "bundle.pem"
add_intermediates_to_bundle = true
EOF
    
    print_success "spiffe-helper config created at /etc/spiffe-helper.conf"
    echo ""
}

create_launchd_services() {
    print_step "Creating launchd services..."
    
    # SPIRE Agent service
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
    print_success "Created SPIRE agent launchd service"
    
    # spiffe-helper service
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
    print_success "Created spiffe-helper launchd service"
    echo ""
}

test_connectivity() {
    print_step "Testing connectivity to SPIRE server..."
    
    if nc -zv -G 5 "$SPIRE_SERVER_IP" "$SPIRE_SERVER_PORT" 2>&1 | grep -q succeeded; then
        print_success "Can reach SPIRE server at ${SPIRE_SERVER_IP}:${SPIRE_SERVER_PORT}"
        return 0
    else
        print_error "Cannot reach SPIRE server at ${SPIRE_SERVER_IP}:${SPIRE_SERVER_PORT}"
        echo -e "${YELLOW}  Check network connectivity and firewall rules${NC}"
        return 1
    fi
    echo ""
}

get_join_token() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}Join Token Required${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Before continuing, you need a join token from the Hliðskjálf platform."
    echo ""
    echo "On the Hliðskjálf machine, run:"
    echo -e "${GREEN}  ./scripts/register-model-server-spire.sh --generate-token${NC}"
    echo ""
    echo -n "Enter join token (or press Enter to skip): "
    read -r JOIN_TOKEN
    
    if [[ -z "$JOIN_TOKEN" ]]; then
        echo -e "${YELLOW}Skipping token registration. You'll need to start the agent manually.${NC}"
        return 1
    fi
    
    return 0
}

start_agent_with_token() {
    local token="$1"
    
    print_step "Starting SPIRE agent with join token..."
    
    # Start agent in background with join token
    sudo /usr/local/bin/spire-agent run \
        -config /opt/spire/conf/agent.conf \
        -joinToken "$token" > /var/log/spire-agent.log 2>&1 &
    
    local agent_pid=$!
    echo "SPIRE agent PID: $agent_pid"
    
    # Wait for socket to appear
    print_step "Waiting for agent socket..."
    local attempts=0
    while [[ ! -S "$SOCKET_PATH" ]] && [[ $attempts -lt 30 ]]; do
        sleep 1
        ((attempts++))
        echo -n "."
    done
    echo ""
    
    if [[ -S "$SOCKET_PATH" ]]; then
        print_success "SPIRE agent socket ready"
        
        # Test health
        if /usr/local/bin/spire-agent healthcheck -socketPath "$SOCKET_PATH" &> /dev/null; then
            print_success "SPIRE agent is healthy"
            return 0
        else
            print_error "SPIRE agent health check failed"
            return 1
        fi
    else
        print_error "SPIRE agent socket not created"
        echo "Check logs: tail -f /var/log/spire-agent.log"
        return 1
    fi
}

load_services() {
    print_step "Loading launchd services..."
    
    # Unload if already loaded
    sudo launchctl unload /Library/LaunchDaemons/com.spiffe.agent.plist 2>/dev/null || true
    sudo launchctl unload /Library/LaunchDaemons/com.spiffe.helper.plist 2>/dev/null || true
    
    sleep 2
    
    # Load services
    sudo launchctl load /Library/LaunchDaemons/com.spiffe.agent.plist
    sudo launchctl load /Library/LaunchDaemons/com.spiffe.helper.plist
    
    print_success "Services loaded"
    echo ""
}

verify_setup() {
    print_step "Verifying setup..."
    
    # Check agent health
    if /usr/local/bin/spire-agent healthcheck -socketPath "$SOCKET_PATH" &> /dev/null; then
        print_success "SPIRE agent is healthy"
    else
        print_error "SPIRE agent health check failed"
    fi
    
    # Check certificates
    sleep 3
    if [[ -f "$CERT_DIR/svid.pem" ]]; then
        print_success "SVID certificate generated"
        
        # Show cert details
        local expiry=$(openssl x509 -in "$CERT_DIR/svid.pem" -noout -enddate 2>/dev/null | cut -d= -f2)
        echo -e "${BLUE}  Certificate expires: $expiry${NC}"
    else
        print_error "SVID certificate not found"
        echo "Check logs: tail -f /var/log/spiffe-helper.log"
    fi
    
    echo ""
}

print_next_steps() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}Setup Complete!${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo ""
    echo "1. Configure your model service (e.g., Ollama) to use SPIRE certificates:"
    echo ""
    echo "   For Ollama:"
    echo -e "   ${GREEN}export OLLAMA_HOST=https://0.0.0.0:6701${NC}"
    echo -e "   ${GREEN}export OLLAMA_CERT_FILE=$CERT_DIR/svid.pem${NC}"
    echo -e "   ${GREEN}export OLLAMA_KEY_FILE=$CERT_DIR/key.pem${NC}"
    echo -e "   ${GREEN}ollama serve${NC}"
    echo ""
    echo "2. Test connection:"
    echo -e "   ${GREEN}curl -k https://localhost:6701/api/tags${NC}"
    echo ""
    echo "3. View logs:"
    echo -e "   ${GREEN}tail -f /var/log/spire-agent.log${NC}"
    echo -e "   ${GREEN}tail -f /var/log/spiffe-helper.log${NC}"
    echo ""
    echo "4. Manage services:"
    echo -e "   ${GREEN}sudo launchctl start com.spiffe.agent${NC}"
    echo -e "   ${GREEN}sudo launchctl stop com.spiffe.agent${NC}"
    echo -e "   ${GREEN}sudo launchctl list | grep spiffe${NC}"
    echo ""
    echo -e "${YELLOW}Certificate Paths:${NC}"
    echo "  - Certificate: $CERT_DIR/svid.pem"
    echo "  - Key:         $CERT_DIR/key.pem"
    echo "  - CA Bundle:   $CERT_DIR/bundle.pem"
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
}

# Main execution
main() {
    print_header
    
    check_prerequisites
    test_connectivity || true  # Continue even if test fails
    download_spire
    download_spiffe_helper
    create_spire_config
    create_spiffe_helper_config
    create_launchd_services
    
    # Try to get join token and start agent
    if get_join_token; then
        if start_agent_with_token "$JOIN_TOKEN"; then
            # Agent started successfully, load helper
            sleep 2
            sudo launchctl load /Library/LaunchDaemons/com.spiffe.helper.plist 2>/dev/null || true
            verify_setup
        else
            echo -e "${YELLOW}Agent failed to start. You can start it manually with:${NC}"
            echo -e "${GREEN}sudo launchctl load /Library/LaunchDaemons/com.spiffe.agent.plist${NC}"
        fi
    else
        echo ""
        echo -e "${YELLOW}To start services manually:${NC}"
        echo -e "${GREEN}1. Get join token from Hliðskjálf platform${NC}"
        echo -e "${GREEN}2. sudo /usr/local/bin/spire-agent run -config /opt/spire/conf/agent.conf -joinToken YOUR_TOKEN${NC}"
        echo -e "${GREEN}3. sudo launchctl load /Library/LaunchDaemons/com.spiffe.helper.plist${NC}"
    fi
    
    print_next_steps
}

# Run main function
main "$@"

