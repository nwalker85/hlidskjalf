"""
Skills System for Norns Agent

Skills are folders containing a SKILL.md file with YAML frontmatter and instructions.
Following Anthropic's pattern for progressive disclosure and token efficiency.

Reference: https://blog.langchain.com/using-skills-with-deep-agents/

All file operations are async to avoid blocking the event loop.
"""

import asyncio
import os
import re
import yaml
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from langchain_core.tools import tool
import aiofiles
import aiofiles.os


@dataclass
class SkillMetadata:
    """Skill metadata extracted from YAML frontmatter."""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "Norns"
    tags: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    path: Path = field(default_factory=Path)


@dataclass  
class Skill:
    """Full skill with metadata and content."""
    metadata: SkillMetadata
    content: str  # Full markdown content (excluding frontmatter)


async def path_exists(path: Path) -> bool:
    """Async check if path exists."""
    return await asyncio.to_thread(path.exists)


async def path_is_dir(path: Path) -> bool:
    """Async check if path is a directory."""
    return await asyncio.to_thread(path.is_dir)


async def list_dir(path: Path) -> list[Path]:
    """Async directory listing."""
    return await asyncio.to_thread(lambda: list(path.iterdir()))


async def read_text_async(path: Path) -> str:
    """Async file read."""
    async with aiofiles.open(path, mode='r') as f:
        return await f.read()


async def write_text_async(path: Path, content: str) -> None:
    """Async file write."""
    async with aiofiles.open(path, mode='w') as f:
        await f.write(content)


async def mkdir_async(path: Path, parents: bool = False, exist_ok: bool = False) -> None:
    """Async directory creation."""
    await asyncio.to_thread(path.mkdir, parents=parents, exist_ok=exist_ok)


async def get_skills_directories() -> list[Path]:
    """Get all directories where skills can be found."""
    dirs = []
    
    # Project skills (relative to workspace)
    project_skills = Path(__file__).parent.parent.parent / "skills"
    if await path_exists(project_skills):
        dirs.append(project_skills)
    
    # User skills (home directory - async to avoid blocking)
    home = await asyncio.to_thread(Path.home)
    user_skills = home / ".hlidskjalf" / "skills"
    if await path_exists(user_skills):
        dirs.append(user_skills)
    
    # Also check current working directory (async to avoid blocking)
    cwd = await asyncio.to_thread(Path.cwd)
    cwd_skills = cwd / "skills"
    if await path_exists(cwd_skills) and cwd_skills not in dirs:
        dirs.append(cwd_skills)
    
    return dirs


def parse_skill_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from SKILL.md content."""
    # Match YAML frontmatter between --- markers
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, content, re.DOTALL)
    
    if match:
        frontmatter = yaml.safe_load(match.group(1))
        body = match.group(2)
        return frontmatter or {}, body
    
    return {}, content


async def load_skill_metadata(skill_path: Path) -> Optional[SkillMetadata]:
    """Load only the metadata from a skill (token efficient)."""
    skill_md = skill_path / "SKILL.md"
    if not await path_exists(skill_md):
        return None
    
    try:
        content = await read_text_async(skill_md)
        frontmatter, _ = parse_skill_frontmatter(content)
        
        return SkillMetadata(
            name=frontmatter.get("name", skill_path.name),
            description=frontmatter.get("description", "No description"),
            version=frontmatter.get("version", "1.0.0"),
            author=frontmatter.get("author", "Unknown"),
            tags=frontmatter.get("tags", []),
            triggers=frontmatter.get("triggers", []),
            dependencies=frontmatter.get("dependencies", []),
            path=skill_path,
        )
    except Exception as e:
        print(f"Error loading skill metadata from {skill_path}: {e}")
        return None


async def load_full_skill(skill_path: Path) -> Optional[Skill]:
    """Load the full skill including content."""
    metadata = await load_skill_metadata(skill_path)
    if not metadata:
        return None
    
    skill_md = skill_path / "SKILL.md"
    content = await read_text_async(skill_md)
    _, body = parse_skill_frontmatter(content)
    
    return Skill(metadata=metadata, content=body.strip())


async def discover_all_skills() -> list[SkillMetadata]:
    """Discover all available skills (metadata only for efficiency)."""
    skills = []
    
    for skills_dir in await get_skills_directories():
        items = await list_dir(skills_dir)
        for item in items:
            if await path_is_dir(item):
                skill_md = item / "SKILL.md"
                if await path_exists(skill_md):
                    metadata = await load_skill_metadata(item)
                    if metadata:
                        skills.append(metadata)
    
    return skills


async def find_skill_by_name(name: str) -> Optional[Path]:
    """Find a skill by name."""
    for skills_dir in await get_skills_directories():
        skill_path = skills_dir / name
        if await path_exists(skill_path):
            skill_md = skill_path / "SKILL.md"
            if await path_exists(skill_md):
                return skill_path
    return None


async def find_matching_skills(query: str) -> list[SkillMetadata]:
    """Find skills that match a query based on triggers, tags, or name."""
    query_lower = query.lower()
    matches = []
    
    for skill in await discover_all_skills():
        # Check triggers
        for trigger in skill.triggers:
            if trigger.lower() in query_lower or query_lower in trigger.lower():
                matches.append(skill)
                break
        else:
            # Check name and tags
            if query_lower in skill.name.lower():
                matches.append(skill)
            elif any(query_lower in tag.lower() for tag in skill.tags):
                matches.append(skill)
    
    return matches


# =============================================================================
# LangChain Tools for Agent (all async)
# =============================================================================

@tool
async def list_skills() -> str:
    """List all available skills with their descriptions and triggers.
    
    Use this to discover what capabilities are available as skills.
    Skills are progressively loaded - only metadata is shown initially.
    """
    skills = await discover_all_skills()
    
    if not skills:
        return "No skills found. You can create new skills using the create_skill tool."
    
    output = ["# Available Skills\n"]
    
    for skill in skills:
        output.append(f"## {skill.name} (v{skill.version})")
        output.append(f"**Description:** {skill.description}")
        output.append(f"**Author:** {skill.author}")
        if skill.tags:
            output.append(f"**Tags:** {', '.join(skill.tags)}")
        if skill.triggers:
            output.append(f"**Triggers:** {', '.join(skill.triggers)}")
        output.append(f"**Path:** {skill.path}")
        output.append("")
    
    return "\n".join(output)


@tool
async def read_skill(skill_name: str) -> str:
    """Read the full content of a skill by name.
    
    Use this when you need to execute a skill or understand its full instructions.
    
    Args:
        skill_name: The name of the skill to read (e.g., 'create-skill', 'deploy-service')
    """
    skill_path = await find_skill_by_name(skill_name)
    
    if not skill_path:
        available = await discover_all_skills()
        names = [s.name for s in available]
        return f"Skill '{skill_name}' not found. Available skills: {', '.join(names) if names else 'none'}"
    
    skill = await load_full_skill(skill_path)
    if not skill:
        return f"Error loading skill '{skill_name}'"
    
    # Include metadata summary and full content
    output = [
        f"# Skill: {skill.metadata.name}",
        f"**Version:** {skill.metadata.version}",
        f"**Description:** {skill.metadata.description}",
        "",
        "---",
        "",
        skill.content,
    ]
    
    # List any supporting files
    supporting_files = []
    items = await list_dir(skill_path)
    for item in items:
        if item.name != "SKILL.md":
            if await path_is_dir(item):
                sub_items = await list_dir(item)
                supporting_files.extend([f"  - {item.name}/{f.name}" for f in sub_items])
            else:
                supporting_files.append(f"  - {item.name}")
    
    if supporting_files:
        output.append("\n---\n## Supporting Files")
        output.extend(supporting_files)
    
    return "\n".join(output)


@tool
async def search_skills(query: str) -> str:
    """Search for skills matching a query.
    
    Searches skill names, descriptions, tags, and triggers.
    
    Args:
        query: Search query (e.g., 'deploy', 'docker', 'create skill')
    """
    matches = await find_matching_skills(query)
    
    if not matches:
        return f"No skills found matching '{query}'. Use list_skills() to see all available skills."
    
    output = [f"# Skills matching '{query}'\n"]
    
    for skill in matches:
        output.append(f"- **{skill.name}**: {skill.description}")
    
    output.append(f"\nUse read_skill(skill_name) to get full instructions.")
    return "\n".join(output)


@tool
async def create_skill(
    name: str,
    description: str,
    content: str,
    tags: str = "",
    triggers: str = "",
    version: str = "1.0.0"
) -> str:
    """Create a new skill that can be used in future sessions.
    
    This is how you learn and persist new capabilities!
    
    Args:
        name: Skill name in kebab-case (e.g., 'deploy-docker', 'analyze-logs')
        description: Brief description of what the skill does
        content: Markdown content with detailed instructions for the skill
        tags: Comma-separated tags (e.g., 'deployment,docker,infrastructure')
        triggers: Comma-separated trigger phrases (e.g., 'deploy a service,start container')
        version: Semantic version (default: 1.0.0)
    
    Returns:
        Success message with skill path, or error message
    """
    # Validate name
    if not re.match(r'^[a-z][a-z0-9-]*$', name):
        return f"Invalid skill name '{name}'. Use kebab-case (e.g., 'my-skill-name')"
    
    # Get the project skills directory
    skills_dir = Path(__file__).parent.parent.parent / "skills"
    await mkdir_async(skills_dir, parents=True, exist_ok=True)
    
    skill_path = skills_dir / name
    
    if await path_exists(skill_path):
        return f"Skill '{name}' already exists at {skill_path}. Use a different name or update the existing skill."
    
    # Create skill directory
    await mkdir_async(skill_path, parents=True)
    
    # Parse tags and triggers
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    trigger_list = [t.strip() for t in triggers.split(",") if t.strip()] if triggers else []
    
    # Build YAML frontmatter
    frontmatter = {
        "name": name,
        "description": description,
        "version": version,
        "author": "Norns",
        "tags": tag_list,
        "triggers": trigger_list,
    }
    
    # Create SKILL.md
    skill_md_content = f"""---
{yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).strip()}
---

{content}
"""
    
    skill_md = skill_path / "SKILL.md"
    await write_text_async(skill_md, skill_md_content)
    
    return f"""✓ Skill '{name}' created successfully!

**Location:** {skill_path}
**Description:** {description}
**Tags:** {', '.join(tag_list) if tag_list else 'none'}
**Triggers:** {', '.join(trigger_list) if trigger_list else 'none'}

The skill is now available. Use read_skill('{name}') to verify."""


@tool
async def update_skill(
    name: str,
    content: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[str] = None,
    triggers: Optional[str] = None,
    version: Optional[str] = None
) -> str:
    """Update an existing skill's content or metadata.
    
    Args:
        name: Name of the skill to update
        content: New markdown content (optional)
        description: New description (optional)
        tags: New comma-separated tags (optional)
        triggers: New comma-separated triggers (optional)
        version: New version (optional)
    
    Returns:
        Success message or error
    """
    skill_path = await find_skill_by_name(name)
    
    if not skill_path:
        return f"Skill '{name}' not found. Use list_skills() to see available skills."
    
    skill_md = skill_path / "SKILL.md"
    current_content = await read_text_async(skill_md)
    frontmatter, body = parse_skill_frontmatter(current_content)
    
    # Update fields if provided
    if description:
        frontmatter["description"] = description
    if tags is not None:
        frontmatter["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if triggers is not None:
        frontmatter["triggers"] = [t.strip() for t in triggers.split(",") if t.strip()]
    if version:
        frontmatter["version"] = version
    if content:
        body = content
    
    # Write updated skill
    updated_content = f"""---
{yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).strip()}
---

{body}
"""
    await write_text_async(skill_md, updated_content)
    
    return f"✓ Skill '{name}' updated successfully at {skill_path}"


# =============================================================================
# Skill Tools Collection
# =============================================================================

SKILL_TOOLS = [
    list_skills,
    read_skill,
    search_skills,
    create_skill,
    update_skill,
]


async def get_skills_context() -> str:
    """Get a context string with available skills for the agent's system prompt."""
    skills = await discover_all_skills()
    
    if not skills:
        return "No skills are currently available. You can create new skills using the create_skill tool."
    
    lines = ["## Available Skills (use read_skill to get full instructions)\n"]
    
    for skill in skills:
        triggers_str = f" | Triggers: {', '.join(skill.triggers)}" if skill.triggers else ""
        lines.append(f"- **{skill.name}**: {skill.description}{triggers_str}")
    
    return "\n".join(lines)
