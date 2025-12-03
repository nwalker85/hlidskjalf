"""
Frigg Context Cache - Local cache for Persona Snapshots

Provides zero-latency access to user context.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Generic, TypeVar

from src.memory.frigg.persona_snapshot import PersonaSnapshot

logger = logging.getLogger(__name__)


class FriggContextCache:
    """
    Thread-safe local cache for Persona Snapshots.
    
    Features:
    - Zero-latency reads from local memory
    - Automatic TTL-based expiration
    - Periodic cleanup of expired entries
    """
    
    def __init__(self, default_ttl_seconds: int = 7200):  # 2 hours default
        self._cache: dict[str, tuple[PersonaSnapshot, float]] = {}
        self._default_ttl = default_ttl_seconds
        self._cleanup_task: asyncio.Task | None = None
    
    async def start(self) -> None:
        """Start background cleanup task"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self) -> None:
        """Stop background cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
    
    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired entries"""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            self._cleanup_expired()
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries"""
        now = datetime.now(timezone.utc).timestamp()
        expired = [
            key for key, (_, expires_at) in self._cache.items()
            if now > expires_at
        ]
        for key in expired:
            del self._cache[key]
        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired persona snapshots")
    
    def get(self, session_id: str) -> PersonaSnapshot | None:
        """
        Get persona snapshot from cache.
        
        Returns None if not found or expired.
        Zero-latency synchronous operation.
        """
        entry = self._cache.get(session_id)
        if entry is None:
            return None
        
        snapshot, expires_at = entry
        if datetime.now(timezone.utc).timestamp() > expires_at:
            del self._cache[session_id]
            return None
        
        return snapshot
    
    def set(
        self, 
        session_id: str, 
        snapshot: PersonaSnapshot, 
        ttl_seconds: int | None = None
    ) -> None:
        """
        Set persona snapshot in cache.
        
        Synchronous operation.
        """
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = datetime.now(timezone.utc).timestamp() + ttl
        self._cache[session_id] = (snapshot, expires_at)
    
    def update(self, session_id: str, **updates) -> PersonaSnapshot | None:
        """
        Update specific fields of a cached persona.
        
        Returns the updated snapshot, or None if not found.
        """
        snapshot = self.get(session_id)
        if snapshot is None:
            return None
        
        # Create updated snapshot
        data = snapshot.model_dump()
        data.update(updates)
        data["last_updated"] = datetime.now(timezone.utc)
        updated = PersonaSnapshot.model_validate(data)
        
        # Re-cache with existing TTL
        entry = self._cache.get(session_id)
        if entry:
            _, expires_at = entry
            self._cache[session_id] = (updated, expires_at)
        
        return updated
    
    def delete(self, session_id: str) -> bool:
        """
        Delete persona from cache.
        
        Returns True if entry existed.
        """
        if session_id in self._cache:
            del self._cache[session_id]
            return True
        return False
    
    def get_by_user(self, user_id: str) -> list[PersonaSnapshot]:
        """Get all personas for a user (across sessions)"""
        now = datetime.now(timezone.utc).timestamp()
        return [
            snapshot for snapshot, expires_at in self._cache.values()
            if snapshot.user_id == user_id and now <= expires_at
        ]
    
    def keys(self) -> list[str]:
        """Get all non-expired session IDs"""
        now = datetime.now(timezone.utc).timestamp()
        return [
            key for key, (_, expires_at) in self._cache.items()
            if now <= expires_at
        ]
    
    def size(self) -> int:
        """Get number of entries"""
        return len(self._cache)
    
    def clear(self) -> None:
        """Clear all entries"""
        self._cache.clear()

