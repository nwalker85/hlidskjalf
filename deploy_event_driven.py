#!/usr/bin/env python3
"""
Event-Driven Multi-Agent Deployment
Uses Redpanda/Kafka for coordination instead of LangChain messages.
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Setup paths
os.chdir(Path(__file__).parent / "hlidskjalf")
sys.path.insert(0, str(Path(__file__).parent / "hlidskjalf"))

from src.norns.deep_agent_system import run_deep_agent_deployment


if __name__ == "__main__":
    print("🔮 Launching Deep Agent System with Subagents...")
    print()
    
    try:
        asyncio.run(run_deep_agent_deployment())
    except KeyboardInterrupt:
        print("\n\n⚠️  Deployment interrupted by Odin")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

