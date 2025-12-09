"""
Procedural Memory - Skills, workflows, and tool usage patterns

Stores how-to knowledge as weighted memory fragments in Muninn.
Procedural memories represent learned behaviors and operational knowledge.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from src.memory.muninn.store import MuninnStore, MemoryFragment, MemoryType

logger = logging.getLogger(__name__)


class ProceduralMemory:
    """
    Procedural memory handler for Muninn.
    
    Stores and retrieves:
    - Skills (agent capabilities)
    - Workflows (multi-step processes)
    - Tool usage patterns (learned behaviors)
    
    All stored as MemoryFragment(type=MemoryType.PROCEDURAL) with:
    - Semantic search via embeddings
    - Weight-based governance via Hel
    - Relationship modeling via Neo4j
    """
    
    def __init__(self, store: MuninnStore):
        self.store = store
    
    async def add_skill(
        self,
        name: str,
        content: str,
        roles: list[str],
        summary: str,
        domain: str = "ravenhelm",
        tags: list[str] | None = None,
        dependencies: list[str] | None = None,
        examples: list[dict] | None = None,
        version: str = "1.0.0",
    ) -> str:
        """
        Store a skill as procedural memory.
        
        Args:
            name: Skill identifier (e.g., "edit-files", "deploy-service")
            content: Full skill instructions (markdown)
            roles: Applicable roles (e.g., ["sre", "devops"])
            summary: 1-2 sentence description for embedding
            domain: Knowledge domain (default: "ravenhelm")
            tags: Categorization tags
            dependencies: Required prerequisite skills
            examples: Few-shot examples
            version: Semantic version
            
        Returns:
            Memory fragment ID
        """
        fragment = MemoryFragment(
            type=MemoryType.PROCEDURAL,
            content=content,
            domain=domain,
            topic="skill",
            summary=summary,
            weight=0.5,  # Initial weight, increases with usage
            features={
                "name": name,
                "roles": roles,
                "tags": tags or [],
                "dependencies": dependencies or [],
                "examples": examples or [],
                "version": version,
                "skill_type": "manual",  # vs "learned" from agent behavior
            },
        )
        
        memory_id = await self.store.remember(fragment)
        logger.info(f"Added skill '{name}' as procedural memory: {memory_id}")
        
        return memory_id
    
    async def add_workflow(
        self,
        name: str,
        steps: list[dict[str, Any]],
        summary: str,
        domain: str = "ravenhelm",
        prerequisites: list[str] | None = None,
        success_rate: float = 0.0,
    ) -> str:
        """
        Store a workflow as procedural memory.
        
        Args:
            name: Workflow identifier
            steps: Ordered workflow steps
            summary: Brief description
            domain: Knowledge domain
            prerequisites: Required skills or conditions
            success_rate: Historical success rate (0.0-1.0)
            
        Returns:
            Memory fragment ID
        """
        # Serialize workflow as structured content
        content_lines = [f"# Workflow: {name}\n", summary, "\n## Steps:\n"]
        for i, step in enumerate(steps, 1):
            action = step.get("action", "")
            desc = step.get("description", "")
            content_lines.append(f"{i}. **{action}**: {desc}")
        
        content = "\n".join(content_lines)
        
        fragment = MemoryFragment(
            type=MemoryType.PROCEDURAL,
            content=content,
            domain=domain,
            topic="workflow",
            summary=summary,
            weight=0.5,
            features={
                "name": name,
                "steps": steps,
                "prerequisites": prerequisites or [],
                "success_rate": success_rate,
                "workflow_type": "sequential",
            },
        )
        
        memory_id = await self.store.remember(fragment)
        logger.info(f"Added workflow '{name}' as procedural memory: {memory_id}")
        
        return memory_id
    
    async def retrieve_skills(
        self,
        query: str,
        role: str | None = None,
        domain: str | None = None,
        k: int = 5,
        min_weight: float = 0.0,
    ) -> list[MemoryFragment]:
        """
        RAG retrieval for relevant skills.
        
        Args:
            query: Natural language query or task description
            role: Filter by role (e.g., "sre", "devops")
            domain: Filter by knowledge domain
            k: Number of skills to return
            min_weight: Minimum weight threshold
            
        Returns:
            List of skill memories, ranked by relevance and weight
        """
        # Retrieve from Muninn with procedural filter
        memories = await self.store.recall(
            query=query,
            k=k * 2,  # Get more candidates for filtering
            memory_type=MemoryType.PROCEDURAL,
            domain=domain,
            min_weight=min_weight,
        )
        
        # Filter by topic=skill (exclude workflows, patterns)
        skills = [m for m in memories if m.topic == "skill"]
        
        # Filter by role if specified
        if role:
            skills = [
                s for s in skills
                if role in s.features.get("roles", [])
            ]
        
        # Return top k
        return skills[:k]
    
    def get_skill_by_name(self, name: str) -> MemoryFragment | None:
        """
        Direct lookup of a skill by name.
        
        Args:
            name: Skill name (e.g., 'file-editing', 'terminal-commands')
            
        Returns:
            MemoryFragment if found, None otherwise
        """
        for fragment in self.store._memory_index.values():
            if (fragment.topic == "skill" and 
                fragment.features.get("name") == name):
                return fragment
        return None
    
    def get_skills_by_names(self, names: list[str]) -> list[MemoryFragment]:
        """
        Direct lookup of multiple skills by name.
        
        Args:
            names: List of skill names
            
        Returns:
            List of MemoryFragments found
        """
        result = []
        for name in names:
            skill = self.get_skill_by_name(name)
            if skill:
                result.append(skill)
        return result
    
    async def retrieve_workflow(
        self,
        query: str,
        domain: str | None = None,
        min_success_rate: float = 0.0,
    ) -> MemoryFragment | None:
        """
        Retrieve the best matching workflow.
        
        Args:
            query: Task or goal description
            domain: Filter by domain
            min_success_rate: Minimum historical success rate
            
        Returns:
            Best matching workflow or None
        """
        memories = await self.store.recall(
            query=query,
            k=10,
            memory_type=MemoryType.PROCEDURAL,
            domain=domain,
        )
        
        # Filter workflows with success rate
        workflows = [
            m for m in memories
            if m.topic == "workflow"
            and m.features.get("success_rate", 0.0) >= min_success_rate
        ]
        
        return workflows[0] if workflows else None
    
    async def get_skill(self, skill_id: str) -> MemoryFragment | None:
        """Get a specific skill by ID."""
        return await self.store.get(skill_id)
    
    async def update_skill(
        self,
        skill_id: str,
        content: str | None = None,
        summary: str | None = None,
        roles: list[str] | None = None,
        tags: list[str] | None = None,
        version: str | None = None,
    ) -> bool:
        """
        Update an existing skill.
        
        Returns True if successful.
        """
        skill = await self.store.get(skill_id)
        if not skill or skill.type != MemoryType.PROCEDURAL:
            return False
        
        # Update fields
        if content is not None:
            skill.content = content
        if summary is not None:
            skill.summary = summary
        if roles is not None:
            skill.features["roles"] = roles
        if tags is not None:
            skill.features["tags"] = tags
        if version is not None:
            skill.features["version"] = version
        
        # Re-embed if content changed
        if content is not None:
            skill.embedding = None  # Will be regenerated
        
        await self.store.remember(skill)
        logger.info(f"Updated skill: {skill_id}")
        
        return True
    
    async def delete_skill(self, skill_id: str) -> bool:
        """
        Delete a skill (actually sets weight to 0 for governance).
        
        Returns True if successful.
        """
        skill = await self.store.get(skill_id)
        if not skill:
            return False
        
        skill.weight = 0.0
        skill.features["deleted"] = True
        
        await self.store.remember(skill)
        logger.info(f"Marked skill as deleted: {skill_id}")
        
        return True
    
    async def list_skills(
        self,
        role: str | None = None,
        domain: str | None = None,
        min_weight: float = 0.1,
    ) -> list[MemoryFragment]:
        """
        List all skills, optionally filtered.
        
        Args:
            role: Filter by role
            domain: Filter by domain
            min_weight: Minimum weight (default 0.1 excludes deleted)
            
        Returns:
            List of skill memories
        """
        # Get all procedural memories from local index
        skills = [
            m for m in self.store._memory_index.values()
            if m.type == MemoryType.PROCEDURAL
            and m.topic == "skill"
            and m.weight >= min_weight
            and not m.features.get("deleted", False)
        ]
        
        # Filter by domain
        if domain:
            skills = [s for s in skills if s.domain == domain]
        
        # Filter by role
        if role:
            skills = [
                s for s in skills
                if role in s.features.get("roles", [])
            ]
        
        # Sort by weight (most used/important first)
        skills.sort(key=lambda s: s.weight, reverse=True)
        
        return skills
    
    async def get_skill_dependencies(
        self,
        skill_id: str,
    ) -> list[MemoryFragment]:
        """
        Get all skills that this skill depends on.
        
        Returns:
            List of dependency skills
        """
        skill = await self.store.get(skill_id)
        if not skill:
            return []
        
        dep_names = skill.features.get("dependencies", [])
        if not dep_names:
            return []
        
        # Find dependencies by name
        dependencies = []
        all_skills = await self.list_skills()
        
        for dep_name in dep_names:
            for s in all_skills:
                if s.features.get("name") == dep_name:
                    dependencies.append(s)
                    break
        
        return dependencies
    
    async def record_skill_usage(
        self,
        skill_id: str,
        success: bool = True,
        context: dict[str, Any] | None = None,
    ) -> None:
        """
        Record that a skill was used (for Hel reinforcement).
        
        Args:
            skill_id: Skill memory ID
            success: Whether the skill was successfully applied
            context: Additional context about the usage
        """
        skill = await self.store.get(skill_id)
        if not skill:
            return
        
        # Touch the memory (updates last_used)
        skill.touch()
        skill.references += 1
        
        # Track usage history
        usage_history = skill.features.get("usage_history", [])
        usage_history.append({
            "timestamp": skill.last_used.isoformat(),
            "success": success,
            "context": context or {},
        })
        skill.features["usage_history"] = usage_history[-100:]  # Keep last 100
        
        # Calculate success rate
        recent_successes = sum(
            1 for u in usage_history[-20:]
            if u.get("success", True)
        )
        skill.features["success_rate"] = recent_successes / min(20, len(usage_history))
        
        await self.store.remember(skill)
        
        # Trigger Hel reinforcement if successful
        if success:
            from src.memory.hel.weight_engine import HelWeightEngine
            hel = HelWeightEngine()
            importance = 1.5 if success else 0.5
            hel.reinforce(skill, importance=importance)
            await self.store.remember(skill)  # Save updated weight
            
        logger.debug(f"Recorded skill usage: {skill.features.get('name')} (success={success})")

