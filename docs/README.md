# Ravenhelm Platform Documentation

## Documentation Structure

```
docs/
├── README.md                    # This file
├── architecture/               # System design & decisions
│   ├── SECURITY_HARDENING_PLAN.md
│   ├── TRAEFIK_MIGRATION_PLAN.md
│   ├── REORGANIZATION.md
│   └── POLICY_ALIGNMENT_AND_COMPLIANCE.md
├── reference/                  # API docs, schemas, guides
│   ├── HOW_TO_CREATE_AGENT_SWARM.md
│   ├── NORNS_DEEP_AGENT_SYSTEM.md
│   ├── README_AGENT_SWARM.md
│   └── TEST_DEEP_AGENT.md
├── runbooks/                   # Operational procedures
│   ├── RUNBOOK-001-deploy-docker-service.md
│   ├── RUNBOOK-002-add-traefik-domain.md
│   ├── RUNBOOK-003-generate-certificates.md
│   └── RUNBOOK-010-deploy-agent.md
├── DEPLOYMENT_SUMMARY.md       # Deployment history
├── EXECUTIVE_SUMMARY.md        # High-level overview
├── FINAL_ACCOMPLISHMENTS.md    # Project achievements
└── NORNS_MISSION_LOG.md        # Agent mission logs
```

---

## Quick Links

### Getting Started
- [Main README](../README.md) - Quick start guide
- [Project Plan](../PROJECT_PLAN.md) - Phased implementation roadmap
- [TODO](../TODO.md) - Current work items

### Architecture
- [Security Hardening](./architecture/SECURITY_HARDENING_PLAN.md) - Zero-trust implementation
- [Traefik Migration](./architecture/TRAEFIK_MIGRATION_PLAN.md) - Edge proxy setup
- [Policy Compliance](./architecture/POLICY_ALIGNMENT_AND_COMPLIANCE.md) - Enterprise alignment

### Runbooks
| Runbook | Purpose |
|---------|---------|
| [RUNBOOK-001](./runbooks/RUNBOOK-001-deploy-docker-service.md) | Deploy new Docker service |
| [RUNBOOK-002](./runbooks/RUNBOOK-002-add-traefik-domain.md) | Add domain to Traefik |
| [RUNBOOK-003](./runbooks/RUNBOOK-003-generate-certificates.md) | Generate/update certificates |
| [RUNBOOK-010](./runbooks/RUNBOOK-010-deploy-agent.md) | Deploy new agent type |

### Reference
- [Creating Agent Swarms](./reference/HOW_TO_CREATE_AGENT_SWARM.md) - Multi-agent architecture
- [Norns Deep Agent](./reference/NORNS_DEEP_AGENT_SYSTEM.md) - Agent system design
- [Testing Guide](./reference/TEST_DEEP_AGENT.md) - How to test agents

---

## Documentation Standards

### Creating New Documents

1. **Choose the right location:**
   - `architecture/` - Design decisions, ADRs, security plans
   - `reference/` - API docs, schemas, how-to guides
   - `runbooks/` - Step-by-step operational procedures

2. **Use consistent naming:**
   - Architecture: `{TOPIC}_PLAN.md` or `{TOPIC}.md`
   - Reference: `{TOPIC}.md` or `HOW_TO_{TOPIC}.md`
   - Runbooks: `RUNBOOK-{NNN}-{name}.md`

3. **Include metadata:**
   ```markdown
   # Document Title

   > **Category:** Architecture | Reference | Runbook  
   > **Last Updated:** YYYY-MM-DD
   ```

### Runbook Requirements

Every runbook MUST include:
- [ ] Prerequisites checklist
- [ ] Step-by-step instructions
- [ ] Verification commands
- [ ] Rollback procedure
- [ ] Troubleshooting section
- [ ] References to related runbooks

---

## RAG Pipeline (Planned)

This documentation is prepared for RAG (Retrieval Augmented Generation) integration:

1. **Markdown structure** optimized for chunking
2. **Consistent headers** for semantic search
3. **Code blocks** with language tags
4. **Cross-references** between documents

Future: The Norns will be able to consult this documentation directly using the Mímir domain intelligence layer.

---

*"The ravens carry knowledge. The documentation preserves it."*

