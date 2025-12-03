"""
Huginn State Cache - Thread-safe local cache with TTL

Provides zero-latency access to session state.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Generic, TypeVar

from src.memory.huginn.state_agent import SessionState

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheEntry(Generic[T]):
    """Cache entry with TTL tracking"""
    
    def __init__(self, value: T, ttl_seconds: int):
        self.value = value
        self.expires_at = datetime.now(timezone.utc).timestamp() + ttl_seconds
    
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc).timestamp() > self.expires_at


class HuginnStateCache:
    """
    Thread-safe local cache for session state.
    
    Features:
    - Zero-latency reads from local memory
    - Automatic TTL-based expiration
    - Periodic cleanup of expired entries
    """
    
    def __init__(self, default_ttl_seconds: int = 3600):
        self._cache: dict[str, CacheEntry[SessionState]] = {}
        self._default_ttl = default_ttl_seconds
        self._cleanup_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
    
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
            await asyncio.sleep(60)  # Check every minute
            await self._cleanup_expired()
    
    async def _cleanup_expired(self) -> None:
        """Remove expired entries"""
        async with self._lock:
            expired = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired:
                del self._cache[key]
            if expired:
                logger.debug(f"Cleaned up {len(expired)} expired cache entries")
    
    def get(self, session_id: str) -> SessionState | None:
        """
        Get session state from cache.
        
        Returns None if not found or expired.
        This is a synchronous, zero-latency operation.
        """
        entry = self._cache.get(session_id)
        if entry is None:
            return None
        if entry.is_expired():
            del self._cache[session_id]
            return None
        return entry.value
    
    def set(self, session_id: str, state: SessionState, ttl_seconds: int | None = None) -> None:
        """
        Set session state in cache.
        
        This is a synchronous operation.
        """
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        self._cache[session_id] = CacheEntry(state, ttl)
    
    def delete(self, session_id: str) -> bool:
        """
        Delete session state from cache.
        
        Returns True if entry existed.
        """
        if session_id in self._cache:
            del self._cache[session_id]
            return True
        return False
    
    def keys(self) -> list[str]:
        """Get all non-expired session IDs"""
        return [
            key for key, entry in self._cache.items()
            if not entry.is_expired()
        ]
    
    def size(self) -> int:
        """Get number of entries (including potentially expired)"""
        return len(self._cache)
    
    def clear(self) -> None:
        """Clear all entries"""
        self._cache.clear()

