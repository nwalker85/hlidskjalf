#!/bin/bash
# Simple remote setup - run from Hliðskjálf platform

set -e

REMOTE="nate@192.168.50.26"
JOIN_TOKEN="f602f7fb-095f-4efc-9a04-422ee9b32bfb"
BACKEND="http://127.0.0.1:6701"
HTTPS_PORT="6701"

echo "Setting up mTLS proxy on $REMOTE..."
echo ""

# Check if Homebrew is installed
echo "▶ Checking Homebrew..."
if ! ssh "$REMOTE" "command -v brew &>/dev/null || test -f /opt/homebrew/bin/brew"; then
    echo "⚠ Homebrew not installed. Installing..."
    ssh -t "$REMOTE" '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo "✓ Homebrew installed"
else
    echo "✓ Homebrew found"
fi
echo ""

# Transfer script
echo "▶ Transferring setup script..."
scp scripts/setup-mtls-proxy-macos.sh "$REMOTE:/tmp/setup.sh"
echo "✓ Transferred"
echo ""

# Run remotely with inputs
echo "▶ Running setup (you may need to enter sudo password)..."
ssh -t "$REMOTE" bash -c "'
# Source Homebrew environment for Apple Silicon
if [[ -f /opt/homebrew/bin/brew ]]; then
    eval \"\$(/opt/homebrew/bin/brew shellenv)\"
fi

cd /tmp
chmod +x setup.sh
echo \"$BACKEND\" | head -1 > /tmp/input1.txt
echo \"$HTTPS_PORT\" | head -1 > /tmp/input2.txt  
echo \"$JOIN_TOKEN\" | head -1 > /tmp/input3.txt
cat /tmp/input1.txt /tmp/input2.txt /tmp/input3.txt | ./setup.sh
'"

echo ""
echo "✓ Setup complete!"

