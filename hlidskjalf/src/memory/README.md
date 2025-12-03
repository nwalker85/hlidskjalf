# Raven Cognitive Memory Architecture

> *The ravens still fly. They still return with what is seen and what is known.*

The cognitive memory system for the Ravenhelm platform, implementing a Norse-themed architecture with reactive blackboard pattern.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RAVEN COGNITIVE MODEL                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   HUGINN (L3/L4)        FRIGG (L2)           MUNINN (Long-term)         │
│   ═══════════════       ═══════════          ═══════════════════        │
│   State Plane           Context Plane        Memory Plane               │
│   ┌───────────┐         ┌───────────┐        ┌───────────────┐          │
│   │  Redis    │────────▶│  Persona  │◀───────│  PostgreSQL   │          │
│   │  + NATS   │         │ Snapshots │        │  + pgvector   │          │
│   └─────┬─────┘         └─────┬─────┘        └───────┬───────┘          │
│         │                     │                      │                   │
│         │                     │                      ▼                   │
│         │                     │              ┌───────────────┐          │
│         │                     │              │    Neo4j +    │          │
│         │                     │              │   Memgraph    │          │
│         │                     │              └───────────────┘          │
│         │                     │                                         │
│         ▼                     ▼                                         │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │                     HEL (Governor)                           │      │
│   │              Reinforce • Decay • Promote • Prune             │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│   MÍMIR (L0/L1)                EVENT FABRIC                             │
│   ═══════════════              ════════════                             │
│   Domain Intelligence          Dual-Stream Events                       │
│   ┌───────────┐                ┌─────────────────────────┐              │
│   │   DIS     │                │  NATS JetStream (hot)   │              │
│   │  1.6.0    │                ├─────────────────────────┤              │
│   │ Dossiers  │                │  Kafka/Redpanda (cold)  │              │
│   └───────────┘                └─────────────────────────┘              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Components

### Huginn - State Plane (`huginn/`)

Odin's raven of thought and perception. Handles real-time, turn-level state.

| File | Purpose |
|------|---------|
| `state_agent.py` | Per-session volatile state in Redis with TTL |
| `state_cache.py` | Zero-latency local cache |
| `nats_subscriber.py` | Real-time event ingestion via JetStream |

**Key Principle**: No synchronous calls in hot path. Agents maintain local caches updated via NATS events.

### Frigg - Context Plane (`frigg/`)

Queen of Asgard who knows all fates. Handles user personalization and Persona Snapshots.

| File | Purpose |
|------|---------|
| `context_agent.py` | Builds context from Huginn + Muninn + Mímir |
| `persona_snapshot.py` | Compact user context (tags, preferences, risks) |
| `context_cache.py` | Local cache for personas |

### Muninn - Memory Plane (`muninn/`)

Odin's raven of memory. Long-term storage with weighted fragments.

| File | Purpose |
|------|---------|
| `store.py` | Main memory store with weight-based retrieval |
| `episodic.py` | Raw experiences and interactions |
| `semantic.py` | Learned patterns from episodes |
| `structural.py` | Knowledge graph (Neo4j + Memgraph) |

### Hel - Memory Governor (`hel/`)

Ruler of the dead. Governs memory lifecycle.

| File | Purpose |
|------|---------|
| `weight_engine.py` | Reinforce (α=0.1) and decay (λ=0.001) |
| `decay_scheduler.py` | Periodic maintenance jobs |
| `promoter.py` | Episodic → Semantic promotion |

**Weighting Model**:
- Reinforcement: `weight += α * importance`
- Decay: `weight *= e^(-λ * hours)`
- Promotion threshold: 0.8 weight, 3+ references
- Prune threshold: <0.1 weight, >24h old

### Mímir - Domain Intelligence (`mimir/`)

Keeper of the Well of Wisdom. DIS 1.6 governed knowledge.

| File | Purpose |
|------|---------|
| `models.py` | DIS 1.6 Pydantic models (Entity, Role, Triplet, etc.) |
| `dossier_loader.py` | Git-backed dossier loading |
| `triplet_engine.py` | AgenticTriplet resolution with JMESPath gates |
| `graph_projection.py` | Sync dossiers to Neo4j |

### Event Fabric (`events/`)

Dual-stream event system for cognitive signals.

| File | Purpose |
|------|---------|
| `schemas.py` | Event types (HuginnTurnEvent, MuninnMemoryEvent, etc.) |
| `nats_producer.py` | Hot-path events via JetStream |
| `kafka_producer.py` | Durable events via Redpanda |

### Ollama Integration (`ollama_provider.py`)

Local LLM for cost-free cognitive operations.

- **nomic-embed-text**: Local embeddings (768 dimensions)
- **llama3.1:8b**: Local chat model for reasoning

## Memory Tools (MCP)

14 tools available to the Norns agent:

| Component | Tools |
|-----------|-------|
| **Huginn** | `huginn_perceive`, `huginn_set_flag` |
| **Frigg** | `frigg_divine`, `frigg_update_tags` |
| **Muninn** | `muninn_recall`, `muninn_remember` |
| **Hel** | `hel_reinforce`, `hel_stats` |
| **Mímir** | `mimir_consult`, `mimir_can_act`, `mimir_entity` |
| **Ollama** | `ollama_analyze`, `ollama_embed`, `ollama_chat` |

## Database Schema

Located in `migrations/versions/001_create_muninn_memories.sql`:

```sql
-- Main memory table with pgvector
CREATE TABLE muninn_memories (
    id UUID PRIMARY KEY,
    type TEXT CHECK (type IN ('episodic', 'semantic', 'procedural')),
    content TEXT NOT NULL,
    embedding vector(1536),
    weight FLOAT DEFAULT 0.5,
    references INTEGER DEFAULT 0,
    ...
);

-- Persona snapshots
CREATE TABLE frigg_personas (...);

-- Episode tracking
CREATE TABLE muninn_episodes (...);

-- Semantic patterns
CREATE TABLE muninn_patterns (...);

-- Governance audit log
CREATE TABLE hel_governance_log (...);
```

## DIS 1.6 Dossier

Domain intelligence stored in `dossiers/ravenhelm/dossier.json`:

- **8 Entities**: Norns Agent, Subagent, User, Session, Memory, Skill, Deployment, Task
- **5 Roles**: Orchestrator, Planner, Worker, User, Admin
- **10 Triplets**: Behavioral grammar for allowed actions
- **7 Access Gates**: RBAC rules with JMESPath conditions

## Usage

```python
from src.memory import (
    HuginnStateAgent,
    FriggContextAgent,
    MuninnStore,
    HelWeightEngine,
    MimirDossierLoader,
    MimirTripletEngine,
)

# Initialize components
huginn = HuginnStateAgent(redis_url="redis://redis:6379")
muninn = MuninnStore(database_url="postgresql://...")
hel = HelWeightEngine()

# Perceive current state
state = huginn.perceive(session_id)

# Recall memories
memories = await muninn.recall("deployment issues", k=5)

# Reinforce useful memories
hel.reinforce(memory, importance=1.5)

# Consult domain knowledge
loader = MimirDossierLoader("dossiers/ravenhelm")
dossier = loader.load_wisdom()
engine = MimirTripletEngine(dossier)
valid_actions = engine.consult("role-orchestrator", context)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://redis:6379` | Huginn state storage |
| `DATABASE_URL` | - | Muninn PostgreSQL connection |
| `NEO4J_URI` | `bolt://neo4j:7687` | Structural memory |
| `NATS_URL` | `nats://nats:4222` | Event fabric (hot) |
| `KAFKA_BOOTSTRAP` | `redpanda:9092` | Event fabric (cold) |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Local LLM |

