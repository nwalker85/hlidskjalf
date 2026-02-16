#!/bin/bash
# Install Homebrew on remote Mac

REMOTE="nate@192.168.50.26"

echo "Installing Homebrew on $REMOTE..."
echo ""

ssh -t "$REMOTE" 'bash -c '"'"'
# Check if Homebrew is already installed
if command -v brew &> /dev/null; then
    echo "✓ Homebrew already installed"
    brew --version
    exit 0
fi

echo "Installing Homebrew..."
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Add Homebrew to PATH for Apple Silicon
if [[ -f "/opt/homebrew/bin/brew" ]]; then
    echo "Adding Homebrew to PATH..."
    echo '\''eval "$(/opt/homebrew/bin/brew shellenv)"'\'' >> ~/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

echo "✓ Homebrew installed successfully"
brew --version
'"'"'

