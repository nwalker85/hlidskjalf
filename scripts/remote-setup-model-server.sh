#!/bin/bash
# =============================================================================
# Remote mTLS Proxy Setup for External Mac
# =============================================================================
# This script remotely sets up the mTLS proxy on an external Mac via SSH
#
# Usage:
#   ./scripts/remote-setup-model-server.sh [user@]host
#
# Example:
#   ./scripts/remote-setup-model-server.sh nate@192.168.50.26
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Remote mTLS Proxy Setup for External Mac                  ║${NC}"
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

# Parse arguments
REMOTE_HOST="${1:-nate@192.168.50.26}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_header

# Check SSH connection
print_step "Testing SSH connection to ${REMOTE_HOST}..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${REMOTE_HOST}" "echo connected" &>/dev/null; then
    echo -e "${YELLOW}SSH key authentication not set up. Will use password authentication.${NC}"
    echo -e "${YELLOW}To avoid password prompts, run: ssh-copy-id ${REMOTE_HOST}${NC}"
    echo ""
fi

# Get configuration
echo -e "${YELLOW}Configuration:${NC}"
echo -n "Backend service URL [http://127.0.0.1:11434]: "
read -r BACKEND_SERVICE
BACKEND_SERVICE="${BACKEND_SERVICE:-http://127.0.0.1:11434}"

echo -n "HTTPS port [6701]: "
read -r HTTPS_PORT
HTTPS_PORT="${HTTPS_PORT:-6701}"

echo -n "SPIRE server IP [10.10.0.10]: "
read -r SPIRE_SERVER_IP
SPIRE_SERVER_IP="${SPIRE_SERVER_IP:-10.10.0.10}"

echo ""

# Generate join token
print_step "Generating SPIRE join token..."
if [[ ! -f "${SCRIPT_DIR}/register-model-server-spire.sh" ]]; then
    print_error "register-model-server-spire.sh not found"
    exit 1
fi

"${SCRIPT_DIR}/register-model-server-spire.sh" --generate-token > /tmp/spire-token-output.txt 2>&1
JOIN_TOKEN=$(grep "Token:" /tmp/spire-token-output.txt | awk '{print $2}')

if [[ -z "$JOIN_TOKEN" ]]; then
    print_error "Failed to generate join token"
    cat /tmp/spire-token-output.txt
    exit 1
fi

print_success "Join token generated"
echo ""

# Transfer setup script
print_step "Transferring setup script to remote host..."
scp "${SCRIPT_DIR}/setup-mtls-proxy-macos.sh" "${REMOTE_HOST}:/tmp/setup-mtls-proxy.sh"
print_success "Script transferred"
echo ""

# Create remote configuration file
print_step "Creating remote configuration..."
ssh "${REMOTE_HOST}" "cat > /tmp/mtls-setup.conf << 'EOF'
BACKEND_SERVICE='${BACKEND_SERVICE}'
HTTPS_PORT='${HTTPS_PORT}'
SPIRE_SERVER_IP='${SPIRE_SERVER_IP}'
JOIN_TOKEN='${JOIN_TOKEN}'
EOF"
print_success "Configuration created"
echo ""

# Create automated setup script on remote
print_step "Creating automated setup on remote host..."
ssh "${REMOTE_HOST}" 'cat > /tmp/run-setup.sh << '"'"'EOFSCRIPT'"'"'
#!/bin/bash
source /tmp/mtls-setup.conf

# Make setup script executable
chmod +x /tmp/setup-mtls-proxy.sh

# Create expect script for automated input
cat > /tmp/setup-expect.exp << '"'"'EOF'"'"'
#!/usr/bin/expect -f
set timeout -1
spawn /tmp/setup-mtls-proxy.sh

# Backend service URL
expect "Backend service URL*:"
send "'"'"'$BACKEND_SERVICE'"'"'\r"

# HTTPS port
expect "HTTPS port*:"
send "'"'"'$HTTPS_PORT'"'"'\r"

# Join token
expect "Enter join token:"
send "'"'"'$JOIN_TOKEN'"'"'\r"

# Handle password prompts for sudo
expect {
    "Password:" {
        send_user "\n\nPlease enter your sudo password on the remote machine:\n"
        interact
        exp_continue
    }
    eof
}
EOF

chmod +x /tmp/setup-expect.exp

# Check if expect is installed
if ! command -v expect &> /dev/null; then
    echo "Installing expect via Homebrew..."
    brew install expect
fi

# Run the setup
/tmp/setup-expect.exp
EOFSCRIPT'

ssh "${REMOTE_HOST}" 'chmod +x /tmp/run-setup.sh'
print_success "Automated setup created"
echo ""

# Run the setup remotely
print_step "Running setup on remote host..."
echo -e "${YELLOW}This may take a few minutes and will prompt for sudo password...${NC}"
echo ""

ssh -t "${REMOTE_HOST}" '/tmp/run-setup.sh'

echo ""
print_success "Remote setup complete!"
echo ""

# Verify
print_step "Verifying setup..."
sleep 2

if ssh "${REMOTE_HOST}" "curl -k -sf https://localhost:${HTTPS_PORT}/health" &>/dev/null; then
    print_success "mTLS proxy is responding!"
else
    print_error "mTLS proxy not responding yet"
    echo -e "${YELLOW}Check logs on remote host:${NC}"
    echo -e "  ssh ${REMOTE_HOST} 'tail -f /var/log/spire-agent.log'"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Remote Management Commands:${NC}"
echo -e "  View logs:    ${GREEN}ssh ${REMOTE_HOST} 'tail -f /usr/local/var/log/nginx/access.log'${NC}"
echo -e "  Restart:      ${GREEN}ssh ${REMOTE_HOST} 'sudo nginx -s reload'${NC}"
echo -e "  Stop:         ${GREEN}ssh ${REMOTE_HOST} 'sudo nginx -s stop'${NC}"
echo ""
echo -e "${YELLOW}Test from platform:${NC}"
echo -e "  ${GREEN}curl https://models.ravenhelm.dev/health${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

