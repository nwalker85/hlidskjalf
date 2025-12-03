#!/bin/bash
# Platform Deployment Orchestrator
# This script launches the multi-agent orchestration system

set -e

cd "$(dirname "$0")"

echo "🔮 Ravenhelm Platform Deployment - Multi-Agent Orchestration"
echo "=" | tr ' ' '=' | head -c 80
echo ""

# Check for required environment
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating template..."
    cat > .env << 'EOF'
# OpenAI API Key (required for agents)
OPENAI_API_KEY=

# Twilio (optional - for SMS notifications)
TWILIO_SID=AC94d0db92da17f5a5b25dbacc7389dae6
TWILIO_NUMBER=+17372143330
TWILIO_AUTH_TOKEN=e5ab75afa96d0ef3e217dd64c5603a1e

# LangFuse (optional - for observability)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
EOF
    echo "❌ Please add your OPENAI_API_KEY to .env and run again"
    exit 1
fi

# Source environment
set -a
source .env
set +a

if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ OPENAI_API_KEY not set in .env file"
    exit 1
fi

echo "✓ Environment configured"
echo ""

# Activate virtual environment
if [ ! -d ".venv313" ]; then
    echo "⚠️  Virtual environment not found. Creating..."
    python3.13 -m venv .venv313
    source .venv313/bin/activate
    pip install -e ./hlidskjalf --quiet
else
    source .venv313/bin/activate
fi

# Set Python path
export PYTHONPATH="$(pwd)/hlidskjalf:$PYTHONPATH"

# Run the orchestration
echo "🚀 Launching Norns orchestrator..."
echo ""

python orchestrate_platform_deployment.py

