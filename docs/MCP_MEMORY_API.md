# MCP Memory API Reference

**Last Updated**: 2025-12-06

This document catalogs all memory-related tools exposed via the Model Context Protocol (MCP) through the Norns agent and Bifrost gateway.

---

## Overview

The Raven Cognitive Architecture exposes a comprehensive memory API via MCP, organized into the following categories:

- **Huginn** (State) — Real-time session and turn-level perception
- **Frigg** (Context) — User persona and personalization
- **Muninn** (Memory) — Long-term episodic and semantic memory
- **Hel** (Governance) — Memory reinforcement and decay
- **Mímir** (Domain Knowledge) — DIS-based domain intelligence
- **Procedural Memory** — Skills management with RAG retrieval
- **Document Ingestion** — Web crawling and semantic document storage
- **Graph Queries** — Neo4j-based skill relationships and workflows
- **Ollama** — Local LLM for embedding and analysis

---

## 🦅 Huginn Tools (State)

### `huginn_perceive`
Perceive the current state for a session.

**Parameters:**
- `session_id` (string): The session ID to perceive

**Returns:** Current session state including utterance, intent, slots, and flags.

---

### `huginn_set_flag`
Set a routing/state flag for a session.

**Parameters:**
- `session_id` (string): The session ID
- `flag` (string): The flag name to set
- `value` (boolean, default: true): The boolean value

**Returns:** Updated state with flags.

---

## 🌟 Frigg Tools (Context)

### `frigg_divine`
Divine the persona/context for a session.

**Parameters:**
- `session_id` (string): The session ID to divine

**Returns:** PersonaSnapshot including user tags, preferences, risk flags, and applicable triplets.

---

### `frigg_update_tags`
Add tags to a user's persona.

**Parameters:**
- `session_id` (string): The session ID
- `tags` (array[string]): List of tags to add

**Returns:** Updated persona with tags.

---

## 🧠 Muninn Tools (Memory)

### `muninn_recall`
Recall memories using semantic search.

**Parameters:**
- `query` (string): The search query
- `k` (integer, default: 5): Number of results to return
- `memory_type` (string, optional): Filter by type (episodic, semantic, procedural)
- `domain` (string, optional): Filter by domain

**Returns:** List of relevant memory fragments ordered by relevance and weight.

---

### `muninn_remember`
Store a new memory in Muninn.

**Parameters:**
- `content` (string): The content to remember
- `domain` (string, default: "general"): Domain category
- `topic` (string, optional): Topic tag
- `user_id` (string, optional): User association
- `session_id` (string, optional): Session association

**Returns:** Created memory info with memory_id.

---

## ⚖️ Hel Tools (Governance)

### `hel_reinforce`
Reinforce a memory (increase its weight).

**Parameters:**
- `memory_id` (string): The memory ID to reinforce
- `importance` (float, default: 1.0): Importance factor (0.0-2.0)

**Returns:** Updated weight and references count.

---

### `hel_stats`
Get memory governance statistics.

**Returns:** Statistics about memory weights, promotion candidates, and prune candidates.

---

## 📚 Mímir Tools (Domain Knowledge)

### `mimir_consult`
Consult Mímir for valid actions (triplets) for a role.

**Parameters:**
- `role_id` (string): The role to query for
- `context` (object, optional): Context for gate evaluation

**Returns:** List of valid AgenticTriplets with mode, target, and stance.

---

### `mimir_can_act`
Check if a role can perform a specific action.

**Parameters:**
- `role_id` (string): The role to check
- `entity_id` (string): The target entity
- `mode` (string): The mode of interaction (CREATE, READ, UPDATE, DELETE, etc.)
- `context` (object, optional): Context for gate evaluation

**Returns:** Permission check result with allowed status and reason if denied.

---

### `mimir_entity`
Get entity definition from Mímir.

**Parameters:**
- `entity_id` (string): The entity ID to look up

**Returns:** Full entity definition from the DIS dossier.

---

## 🛠️ Procedural Memory Tools (Skills)

### `skills_list`
List all skills (procedural memories).

**Parameters:**
- `role` (string, optional): Filter by role (e.g., "sre", "devops")
- `domain` (string, optional): Filter by domain
- `min_weight` (float, default: 0.1): Minimum weight threshold

**Returns:** List of skills with metadata (id, name, summary, roles, weight, version).

---

### `skills_retrieve`
Retrieve relevant skills using RAG (semantic search).

**Parameters:**
- `query` (string): Task description or search query
- `role` (string, optional): Role filter
- `domain` (string, optional): Domain filter
- `k` (integer, default: 5): Number of skills to retrieve

**Returns:** List of relevant skills with full content, ordered by relevance.

**Use Case:** This is the primary tool for RAG-based skill injection. Norns calls this before spawning subagents to get relevant skills for the task.

---

### `skills_add`
Add a new skill to procedural memory.

**Parameters:**
- `name` (string): Skill identifier (kebab-case)
- `content` (string): Full skill instructions (markdown)
- `roles` (array[string]): Applicable roles (e.g., ["sre", "devops"])
- `summary` (string): Brief description
- `domain` (string, default: "ravenhelm"): Knowledge domain
- `tags` (array[string], optional): Tags
- `dependencies` (array[string], optional): Prerequisite skills

**Returns:** Created skill info with skill_id and name.

---

### `skills_update`
Update an existing skill.

**Parameters:**
- `skill_id` (string): Skill memory ID
- `content` (string, optional): New content
- `summary` (string, optional): New summary
- `roles` (array[string], optional): New roles
- `tags` (array[string], optional): New tags

**Returns:** Update status with skill_id.

---

### `skills_delete`
Delete a skill (sets weight to 0).

**Parameters:**
- `skill_id` (string): Skill memory ID

**Returns:** Deletion status.

---

## 📄 Document Ingestion Tools

### `documents_crawl_page`
Crawl a single web page and store in semantic memory.

Uses Firecrawl to extract LLM-friendly content.

**Parameters:**
- `url` (string): Page URL to crawl
- `domain` (string, default: "external"): Domain classification

**Returns:** Crawl results with memory IDs and chunk count.

---

### `documents_crawl_site`
Crawl an entire website and store pages in semantic memory.

**Parameters:**
- `url` (string): Root URL to crawl
- `domain` (string, default: "external"): Domain classification
- `max_depth` (integer, default: 2): Maximum link depth
- `max_pages` (integer, default: 50): Maximum pages to crawl

**Returns:** Crawl statistics including pages processed and memory IDs.

---

### `documents_search`
Search ingested documents.

**Parameters:**
- `query` (string): Search query
- `domain` (string, optional): Domain filter
- `limit` (integer, default: 10): Maximum results

**Returns:** Matching documents with content and metadata.

---

### `documents_stats`
Get statistics about ingested documents.

**Parameters:**
- `domain` (string, optional): Domain filter

**Returns:** Document statistics including count, domains, and storage info.

---

## 🕸️ Graph Query Tools (Neo4j)

### `graph_skill_dependencies`
Get dependencies for a skill from Neo4j graph.

**Parameters:**
- `skill_id` (string): Skill memory ID
- `recursive` (boolean, default: true): Include transitive dependencies

**Returns:** List of required skills with ID, name, and summary.

---

### `graph_skills_for_role`
Get all skills available to a role from Neo4j graph.

**Parameters:**
- `role_id` (string): Role identifier (e.g., "sre")
- `include_inherited` (boolean, default: true): Include parent role skills

**Returns:** List of authorized skills with weights.

---

### `graph_skill_workflow`
Get typical workflow sequence starting from a skill.

Follows FOLLOWS relationships to build workflow chain.

**Parameters:**
- `start_skill_id` (string): Starting skill ID

**Returns:** Ordered workflow steps with names and summaries.

---

## 🦙 Ollama Tools (Local LLM)

### `ollama_analyze`
Use local Ollama model for analysis tasks.

Runs locally without API costs.

**Parameters:**
- `content` (string): The content to analyze
- `task` (string, default: "summarize"): The analysis task (summarize, extract_entities, classify, reason)
- `context` (string, optional): Context to guide analysis

**Returns:** Analysis result from local model.

**Use Cases:** Summarization, entity extraction, classification, reasoning.

---

### `ollama_embed`
Get embeddings using local Ollama model.

**Parameters:**
- `text` (string): Text to embed

**Returns:** Embedding vector info with dimension and preview.

**Use Cases:** Similarity comparisons, semantic search preparation, clustering.

---

### `ollama_chat`
Chat with local Ollama model for cognitive tasks.

**Parameters:**
- `message` (string): The message to send
- `system_prompt` (string, optional): System prompt for context

**Returns:** Chat response from local model.

**Use Cases:** Breaking down complex problems, generating alternatives, validating reasoning.

---

## Architecture Integration

### Norns Agent
All tools are automatically available to the Norns agent via LangGraph's tool binding. The agent can call any tool during execution.

### Bifrost Gateway
The Bifrost gateway's MCP backend can discover and call these tools via:
- `/tools/list` — Get all available tools
- `/tools/call` — Invoke a specific tool

### MCP Protocol
Standard MCP JSON-RPC format:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "skills_retrieve",
    "arguments": {
      "query": "edit files safely using workspace tools",
      "role": "sre",
      "k": 5
    }
  },
  "id": 1
}
```

---

## Security

All MCP endpoints are protected by:
- **OAuth2 via Zitadel** — All requests require valid OAuth tokens
- **SPIRE mTLS** — Internal service-to-service communication uses SPIRE identities
- **Traefik Gateway** — Single ingress point with certificate validation
- **Scope-based Authorization** — Tools check for required scopes (e.g., `mcp.memory.write`)

See `docs/runbooks/RUNBOOK-023-mcp-gitlab-server.md` for security details.

---

## Usage Examples

### Example 1: RAG Skills Retrieval for Subagent

```python
# Norns retrieves relevant skills before spawning a subagent
skills = await skills_retrieve(
    query="edit configuration files, verify changes, handle errors",
    role="sre",
    k=3
)

# Skills are injected into subagent system prompt
subagent_prompt = f"""
You are Norns-SRE, a specialized SRE agent.

## Relevant Skills:
{'\n\n'.join(skill['content'] for skill in skills)}

Now handle the task...
"""
```

### Example 2: Document Ingestion from Website

```python
# Crawl documentation site
result = await documents_crawl_site(
    url="https://docs.example.com",
    domain="product_docs",
    max_depth=3,
    max_pages=100
)

# Later, search for relevant content
docs = await documents_search(
    query="how to configure authentication",
    domain="product_docs",
    limit=5
)
```

### Example 3: Graph-Based Skill Discovery

```python
# Find skills for a specific role
sre_skills = await graph_skills_for_role(
    role_id="sre",
    include_inherited=True
)

# Get dependencies for a complex skill
deps = await graph_skill_dependencies(
    skill_id="deploy-application",
    recursive=True
)

# Get workflow sequence
workflow = await graph_skill_workflow(
    start_skill_id="incident-response"
)
```

---

## Future Enhancements

- **Memory Admin UI** — Web interface for managing skills, documents, and memories
- **Firecrawl Integration** — Automatic sitemap processing and scheduled crawls
- **Weaviate Hybrid Search** — Enhanced semantic search with reranking
- **Hel Auto-Governance** — Automatic memory promotion and pruning
- **Cross-Repo Skill Sharing** — DIS-based skill distribution across projects

---

## Related Documentation

- `docs/architecture/RAVEN_COGNITIVE_ARCHITECTURE.md` — Overall cognitive design
- `docs/runbooks/RUNBOOK-023-mcp-gitlab-server.md` — MCP server patterns
- `docs/runbooks/RUNBOOK-026-llm-configuration-system.md` — LLM configuration
- `src/memory/README.md` — Memory system implementation details
- `hlidskjalf/src/norns/memory_tools.py` — Tool implementations

