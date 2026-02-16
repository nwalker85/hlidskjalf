---
name: memory-retrieval
description: Retrieve relevant documentation, runbooks, and knowledge from Muninn long-term memory
version: 1.0.0
author: Norns
roles:
  - sre
  - devops
  - technical_writer
  - governance
summary: >
  Use memory tools to retrieve relevant docs, runbooks, ADRs, and specs before drafting answers.
  Query Muninn with specific domains, doc types, and retrieval modes to find authoritative knowledge.
tags:
  - memory
  - retrieval
  - muninn
  - documentation
  - knowledge
triggers:
  - find documentation
  - search runbook
  - lookup ADR
  - retrieve knowledge
  - check memory
---

# Memory Retrieval from Muninn

Before drafting answers or making decisions, retrieve relevant documentation, runbooks, and knowledge from Muninn (long-term memory).

## Why Use Memory Tools?

**Don't assume. Retrieve.**

- ✅ Get the ACTUAL architecture, not what you think it is
- ✅ Find EXISTING runbooks instead of recreating procedures
- ✅ Reference DOCUMENTED decisions (ADRs) instead of guessing
- ✅ Cite REAL file paths and IDs, not invented ones

## The Retrieval Pattern

### 1. Identify What You Need

Before querying, determine:
- **Domain**: Which system/project? (ravenhelm-platform, gitlab-sre, telephony)
- **Doc Types**: What kind of document? (runbook, wiki, adr, plan, spec)
- **Retrieval Mode**: What's the query focus? (design, runbook, architecture, troubleshooting)
- **Query Text**: Short, focused description of what you need

### 2. Call Memory Tools

```python
memories = await muninn_recall(
    query="traefik configuration and routing setup",
    k=5,
    memory_type="semantic",  # or "episodic", "procedural"
    domain="ravenhelm"
)
```

### 3. Read the Retrieved Chunks

Muninn returns memory fragments with:
- `content`: The actual text from the document
- `domain`: Which domain it came from
- `weight`: How relevant/trusted this memory is
- `references`: How often it's been used

### 4. Cite File Paths and IDs

When using retrieved information:
- Reference runbook IDs: "Per RUNBOOK-024, add services via..."
- Cite file paths: "As documented in `docs/runbooks/RUNBOOK-024-add-shared-service.md`..."
- Link to ADRs: "ADR-003 specifies that..."

### 5. Don't Assume Missing Info

If memory retrieval returns nothing or insufficient info:
- ❌ DON'T: Make up procedures or architecture
- ✅ DO: State "I couldn't find documentation for X in memory. Shall I create it?"

## Retrieval Modes

### Design Mode
**Use when**: Planning new features or architecture

```python
memories = await muninn_recall(
    query="SPIRE mTLS certificate rotation design",
    memory_type="semantic",
    domain="ravenhelm"
)
```

**Expect to find**: ADRs, architecture docs, design specs

### Runbook Mode
**Use when**: Executing operational tasks

```python
memories = await muninn_recall(
    query="adding a new shared service with traefik",
    memory_type="semantic",
    domain="ravenhelm"
)
```

**Expect to find**: Step-by-step runbooks, HOWTOs

### Architecture Mode
**Use when**: Understanding system structure

```python
memories = await muninn_recall(
    query="event-driven architecture with NATS and Kafka",
    memory_type="semantic",
    domain="ravenhelm"
)
```

**Expect to find**: Architecture diagrams, component docs, system overviews

### Troubleshooting Mode
**Use when**: Diagnosing issues

```python
memories = await muninn_recall(
    query="docker network connectivity issues",
    memory_type="episodic",  # Past incidents
    domain="ravenhelm"
)
```

**Expect to find**: Past incidents, known issues, fixes

## Domain-Specific Queries

### Ravenhelm Platform
```python
# Query for platform-wide knowledge
memories = await muninn_recall(
    query="shared services postgres redis zitadel",
    domain="ravenhelm"
)
```

**Common topics**: Traefik, SPIRE, platform_net, shared services

### GitLab SRE
```python
# Query for GitLab-specific knowledge
memories = await muninn_recall(
    query="gitlab webhook configuration norns automation",
    domain="gitlab-sre"
)
```

**Common topics**: GitLab API, webhook payloads, issue taxonomy

### Telephony Systems
```python
# Query for voice/telephony knowledge
memories = await muninn_recall(
    query="LiveKit SIP trunk configuration",
    domain="telephony"
)
```

**Common topics**: LiveKit, Twilio, RavenVoice, SIP

## Document Type Filters

### Runbooks
```python
# Find operational procedures
memories = await muninn_recall(
    query="backup postgres database to s3",
    memory_type="procedural"  # Runbooks are procedural memories
)
```

**Use for**: Step-by-step procedures, operational tasks

### ADRs (Architecture Decision Records)
```python
# Find past architectural decisions
memories = await muninn_recall(
    query="why did we choose traefik over nginx",
    memory_type="semantic"  # ADRs are semantic knowledge
)
```

**Use for**: Understanding design rationale, technology choices

### Wiki Pages
```python
# Find conceptual documentation
memories = await muninn_recall(
    query="raven cognitive architecture overview",
    memory_type="semantic"
)
```

**Use for**: Concepts, overviews, explanations

### Plans & Specs
```python
# Find project plans or specifications
memories = await muninn_recall(
    query="phase 6 ai infrastructure roadmap",
    memory_type="semantic"
)
```

**Use for**: Roadmaps, feature specs, milestones

## Combining Multiple Queries

For complex tasks, make multiple focused queries:

```python
# Step 1: Get the design rationale
design = await muninn_recall(
    query="SPIRE SPIFFE identity design decisions",
    memory_type="semantic"
)

# Step 2: Get the operational procedure
procedure = await muninn_recall(
    query="register new SPIRE workload identity",
    memory_type="procedural"
)

# Step 3: Get past incidents for context
incidents = await muninn_recall(
    query="SPIRE certificate rotation failures",
    memory_type="episodic"
)

# Now you have: WHY (design), HOW (procedure), WHAT WENT WRONG (incidents)
```

## Working with Retrieved Memories

### Extract File Paths
```python
for memory in memories:
    content = memory["content"]
    # Look for file references
    if "docs/runbooks/RUNBOOK-" in content:
        # Extract and cite
        print(f"Reference: {extract_runbook_id(content)}")
```

### Check Memory Weight
```python
for memory in memories:
    if memory["weight"] < 0.3:
        print("⚠️  Low-weight memory, may be outdated")
    elif memory["weight"] > 0.7:
        print("✓ High-weight memory, frequently referenced")
```

### Prefer Recent Memories
```python
# Muninn orders by relevance + weight
# First result is usually best
best_match = memories[0]

# But check if it's actually relevant
if best_match["domain"] != expected_domain:
    print("⚠️  Cross-domain result, verify applicability")
```

## Citing Sources in Responses

### Good Citation Examples

```markdown
✓ "Per RUNBOOK-024 (Add Shared Service), the steps are:
   1. Register in port_registry.yaml
   2. Add Traefik labels
   3. Update dynamic.yml"

✓ "According to docs/architecture/SPIRE_DESIGN.md, all workloads
   must register SVIDs using spiffe-helper configs."

✓ "ADR-003 documents the decision to use Traefik:
   - Single ingress point
   - Automatic service discovery
   - Built-in Let's Encrypt support"
```

### Bad Citation Examples

```markdown
❌ "I think we use Traefik..."
   (Use memory retrieval instead of guessing)

❌ "The runbook says to..."
   (Which runbook? Cite the ID)

❌ "Documentation somewhere mentions..."
   (Be specific with file paths)
```

## When Memory is Empty or Insufficient

### No Results Found
```
"I searched Muninn for 'X' but found no existing documentation.

Options:
1. Create new runbook/doc for this
2. Check if this is documented elsewhere (different domain?)
3. Verify the feature actually exists"
```

### Conflicting Information
```
"Muninn returned 2 conflicting approaches:
- Memory A (weight 0.8): Use approach X
- Memory B (weight 0.4): Use approach Y

Memory A has higher weight and more references, suggesting it's the current standard."
```

### Outdated Information
```
"Retrieved memory references 'nginx' but current architecture uses 'traefik'.

This memory may be outdated (weight 0.3, last referenced 6 months ago).
Recommend searching for more recent traefik documentation."
```

## Integration with Other Skills

- **File Editing**: Retrieve runbooks before modifying configs
- **Terminal Commands**: Check memory for known issues before running diagnostics
- **Docker Operations**: Look up service-specific procedures

## Advanced: Skills Retrieval

For procedural knowledge (skills), use the specialized skills tools:

```python
skills = await skills_retrieve(
    query="deploy docker compose with traefik labels",
    role="sre",
    k=3
)
```

Skills are a type of procedural memory optimized for agent instructions.

## Troubleshooting

**Problem**: Too many irrelevant results
- **Solution**: Be more specific in query ("traefik routing" not just "routing")
- **Solution**: Filter by domain and memory_type

**Problem**: No results but you know docs exist
- **Solution**: Try different query terms (synonyms, alternate phrases)
- **Solution**: Check if you're querying the right domain

**Problem**: Retrieved memory seems outdated
- **Solution**: Check weight and last_used timestamp
- **Solution**: Cross-reference with recent episodic memories

## Summary

**Memory Retrieval Pattern:**
1. **Identify** what you need (domain, doc type, mode)
2. **Query** Muninn with specific parameters
3. **Read** the retrieved chunks
4. **Cite** file paths and IDs in your response
5. **Don't assume** if memory is empty

**Always retrieve before inventing.** Muninn holds the authoritative knowledge.

