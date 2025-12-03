"""
Muninn - The Memory Plane

Odin's raven of memory - carries the accumulated shape of everything the system knows.

Three memory types:
- Episodic: Raw interactions, transcripts, user-specific experiences
- Semantic: Learned patterns, stable correlations, embeddings
- Structural: Knowledge graph in Neo4j (domain relationships)
"""

from src.memory.muninn.store import MuninnStore, MemoryFragment, MemoryType
from src.memory.muninn.episodic import EpisodicMemory, Episode
from src.memory.muninn.semantic import SemanticMemory, Pattern

__all__ = [
    "MuninnStore",
    "MemoryFragment",
    "MemoryType",
    "EpisodicMemory",
    "Episode",
    "SemanticMemory",
    "Pattern",
]

