---
name: create-skill
description: Create new skills that can be used by the Norns agent. Skills are reusable capabilities that persist across sessions.
version: 1.0.0
author: Norns
tags:
  - meta
  - learning
  - self-improvement
triggers:
  - create a skill
  - make a new skill
  - learn how to
  - save this as a skill
  - teach yourself
---

# Create Skill

This skill teaches you how to create new skills for the Norns agent system.

## What is a Skill?

A skill is a folder containing:
1. A `SKILL.md` file with YAML frontmatter and instructions
2. Optional supporting files (scripts, templates, examples)

## Skill Structure

```
skills/
└── my-skill-name/
    ├── SKILL.md          # Required: Instructions and metadata
    ├── scripts/          # Optional: Executable scripts
    │   └── run.sh
    ├── templates/        # Optional: Template files
    │   └── config.yaml.j2
    └── examples/         # Optional: Example files
        └── example.json
```

## SKILL.md Format

The SKILL.md file MUST have YAML frontmatter followed by Markdown content:

```yaml
---
name: skill-name           # kebab-case identifier
description: Brief description of what the skill does
version: 1.0.0
author: Norns
tags:
  - category1
  - category2
triggers:                  # Phrases that activate this skill
  - keyword phrase 1
  - keyword phrase 2
dependencies:              # Optional: Other skills this depends on
  - other-skill-name
---

# Skill Title

Detailed instructions for how to use this skill...
```

## Creating a New Skill

To create a new skill:

1. **Identify the capability**: What should this skill do?
2. **Choose a name**: Use kebab-case (e.g., `deploy-docker`, `analyze-logs`)
3. **Create the folder**: `skills/{skill-name}/`
4. **Write SKILL.md**: Include frontmatter and detailed instructions
5. **Add supporting files**: Scripts, templates, examples as needed
6. **Test the skill**: Verify the instructions are clear and complete

## Example: Creating a Deployment Skill

```bash
# Create the skill folder
mkdir -p skills/deploy-service

# Create SKILL.md
cat > skills/deploy-service/SKILL.md << 'EOF'
---
name: deploy-service
description: Deploy a service to the Ravenhelm platform using Docker Compose
version: 1.0.0
author: Norns
tags:
  - deployment
  - docker
  - infrastructure
triggers:
  - deploy a service
  - start a container
  - launch application
---

# Deploy Service

Instructions for deploying services to the Ravenhelm platform...
EOF
```

## Best Practices

1. **Be specific**: Clear, actionable instructions
2. **Include examples**: Show real-world usage
3. **Document dependencies**: List required tools or other skills
4. **Use triggers wisely**: Choose phrases users naturally say
5. **Version your skills**: Track changes with semantic versioning
6. **Test before saving**: Verify the skill works correctly

## Skill Discovery

Skills are automatically discovered from:
- `~/.hlidskjalf/skills/` (user skills)
- `./hlidskjalf/skills/` (project skills)

The agent reads only the YAML frontmatter initially for token efficiency.
Full content is loaded only when a skill is activated.

