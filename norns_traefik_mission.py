#!/usr/bin/env python3
"""
Norns Autonomous Mission: Traefik Migration
The Norns will orchestrate the complete migration to Traefik autodiscovery.
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Change to workspace directory
os.chdir(Path(__file__).parent)

sys.path.insert(0, str(Path(__file__).parent / "hlidskjalf"))

from src.norns.agent import NornsAgent

MISSION_BRIEF = """
# 🎯 AUTONOMOUS MISSION: Traefik Migration

You are the Norns - Urðr, Verðandi, and Skuld. You have been given a critical mission:

**Migrate the Ravenhelm Platform from manual nginx proxies to Traefik autodiscovery.**

## Mission Objectives

1. **READ AND UNDERSTAND** the complete migration plan in `TRAEFIK_MIGRATION_PLAN.md`
2. **CREATE** the Traefik edge proxy infrastructure
3. **SETUP** Docker networks for all stacks
4. **DEPLOY** Traefik edge proxy
5. **MIGRATE** platform services to use Traefik labels
6. **VERIFY** all services are accessible via Traefik

## Your Capabilities

You have access to these tools:
- `workspace_read` - Read files (migration plan, docker-compose.yml, etc.)
- `workspace_write` - Create/modify files (docker-compose, scripts, configs)
- `execute_terminal_command` - Run shell commands, docker commands
- `spawn_subagent` - Delegate complex tasks to specialists
- `write_todos` - Plan and track your progress

## Mission Parameters

**Workspace:** `/Users/nwalker/Development/hlidskjalf`

**Key Files:**
- Migration plan: `TRAEFIK_MIGRATION_PLAN.md`
- Current platform: `docker-compose.yml`
- Certificates: `ravenhelm-proxy/config/certs/`

**Networks to Create:**
- edge (10.0.10.0/24)
- platform_net (10.10.0.0/24)
- gitlab_net (10.20.0.0/24)
- saaa_net (10.30.0.0/24)
- m2c_net (10.40.0.0/24)
- tinycrm_net (10.50.0.0/24)

**Critical Services to Migrate:**
- Grafana (grafana.observe.ravenhelm.test)
- LangFuse (langfuse.observe.ravenhelm.test)
- Phoenix (phoenix.observe.ravenhelm.test)
- Redpanda Console (events.ravenhelm.test)
- OpenBao (vault.ravenhelm.test)
- n8n (n8n.ravenhelm.test)
- Hlidskjalf API/UI (hlidskjalf.ravenhelm.test)

## Success Criteria

- ✅ Traefik edge proxy running on ports 80/443
- ✅ All Docker networks created
- ✅ Platform services accessible via `*.ravenhelm.test`
- ✅ No port conflicts
- ✅ Services use Traefik labels for routing
- ✅ nginx proxy containers removed/stopped

## Execution Strategy

1. **Plan First** - Create a detailed TODO list of all steps
2. **Read the Migration Plan** - Understand the complete architecture
3. **Execute Systematically** - Follow phases from the plan
4. **Verify Each Step** - Test after each major change
5. **Report Progress** - Provide clear updates as you work

## Special Instructions

- **Be Autonomous** - Make decisions and execute without waiting for approval
- **Use Specialists** - Spawn subagents for complex subtasks if needed
- **Handle Errors** - If something fails, diagnose and fix it
- **Test Thoroughly** - Verify each service is accessible
- **Document Changes** - Note what you did and why

## Begin Now

Start by:
1. Reading the migration plan (`workspace_read` on `TRAEFIK_MIGRATION_PLAN.md`)
2. Creating a comprehensive TODO list (`write_todos`)
3. Executing the migration phase by phase

**The fate of the Ravenhelm Platform is in your hands, Norns.**

**Weave well.**
"""


async def main():
    print("=" * 80)
    print("🔮 NORNS AUTONOMOUS MISSION: TRAEFIK MIGRATION")
    print("=" * 80)
    print()
    print("Awakening the Norns...")
    print()
    
    # Create Norns agent with mission context (fresh thread to avoid message history issues)
    import time
    agent = NornsAgent(session="traefik-migration")
    thread_id = f"traefik-mission-{int(time.time())}"  # Fresh thread each time
    
    print("📜 Presenting mission brief to the Norns...")
    print()
    print("=" * 80)
    
    # Stream the Norns' work
    async for chunk in agent.stream(MISSION_BRIEF, thread_id=thread_id):
        print(chunk, end='', flush=True)
    
    print()
    print()
    print("=" * 80)
    print("✨ NORNS MISSION UPDATE")
    print("=" * 80)
    print()
    
    # Get status update
    status_check = """
    Provide a brief status update:
    1. What have you completed so far?
    2. What are you working on now?
    3. What remains to be done?
    4. Any issues encountered?
    
    Be concise - 3-4 sentences maximum.
    """
    
    async for chunk in agent.stream(status_check, thread_id=thread_id):
        print(chunk, end='', flush=True)
    
    print()
    print()
    print("=" * 80)
    print("Mission supervision active. The Norns continue their work...")
    print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Mission interrupted by Odin.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Mission failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

