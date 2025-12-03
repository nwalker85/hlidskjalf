# Hliðskjálf - Odin's High Seat

The Norns Agent System - A self-aware, skill-based AI agent platform.

## Overview

Hliðskjálf (pronounced "hlith-skyalf") is Odin's watchtower in Norse mythology, from which he could observe all the Nine Realms. This package implements the Norns agent - three sisters who weave the threads of fate.

## Features

- **Skills System**: Progressively-loaded, persistent capabilities
- **Self-Awareness**: Agent can view and modify its own code
- **Subagent Spawning**: Create new specialized agents as Docker containers
- **LangGraph Integration**: Built on LangGraph for reliable agent execution

## Components

- `src/norns/agent.py` - Core agent logic
- `src/norns/tools.py` - 40+ available tools
- `src/norns/skills.py` - Skills discovery and creation
- `src/norns/self_awareness.py` - Introspection and self-modification
- `src/norns/subagent_spawner.py` - Dynamic agent creation

## Usage

```python
from src.norns.agent import NornsAgent

agent = NornsAgent()
response = agent.invoke("What can you do?")
```

## License

Proprietary - Ravenhelm Platform
