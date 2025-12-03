"""
Redis-backed short-term memory utilities for the Norns.
"""

from __future__ import annotations

import json
from typing import Iterable, Sequence

import redis
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.messages import BaseMessage

from src.core.config import get_settings


class RedisShortTermMemory:
    """
    Wraps LangChain's RedisChatMessageHistory and adds a lightweight
    key-value store for tracking TODO lists and other per-thread metadata.
    """

    def __init__(
        self,
        redis_url: str,
        ttl_seconds: int,
        key_prefix: str = "norns",
    ) -> None:
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix
        self._kv = redis.Redis.from_url(redis_url, decode_responses=True)

    def _history(self, thread_id: str) -> RedisChatMessageHistory:
        return RedisChatMessageHistory(
            session_id=f"{self.key_prefix}:thread:{thread_id}",
            url=self.redis_url,
            ttl=self.ttl_seconds,
        )

    def load_messages(self, thread_id: str) -> list[BaseMessage]:
        history = self._history(thread_id)
        return list(history.messages)

    def append_messages(self, thread_id: str, messages: Sequence[BaseMessage]) -> None:
        history = self._history(thread_id)
        for message in messages:
            history.add_message(message)

    def clear_messages(self, thread_id: str) -> None:
        history = self._history(thread_id)
        history.clear()

    # -------------------------------------------------------------------------
    # TODO storage
    # -------------------------------------------------------------------------
    def _todo_key(self, thread_id: str) -> str:
        return f"{self.key_prefix}:todos:{thread_id}"

    def load_todos(self, thread_id: str) -> list[dict]:
        raw = self._kv.get(self._todo_key(thread_id))
        if not raw:
            return []
        try:
            todos = json.loads(raw)
            if isinstance(todos, list):
                return todos
        except json.JSONDecodeError:
            pass
        return []

    def save_todos(self, thread_id: str, todos: Iterable[dict]) -> None:
        payload = json.dumps(list(todos))
        self._kv.setex(self._todo_key(thread_id), self.ttl_seconds, payload)

    def clear_todos(self, thread_id: str) -> None:
        self._kv.delete(self._todo_key(thread_id))


_memory: RedisShortTermMemory | None = None


def get_short_term_memory() -> RedisShortTermMemory | None:
    """Return a memoized RedisShortTermMemory if configured."""
    global _memory  # noqa: PLW0603
    if _memory is not None:
        return _memory

    settings = get_settings()
    redis_url = settings.REDIS_URL
    if not redis_url:
        return None

    try:
        _memory = RedisShortTermMemory(
            redis_url=redis_url,
            ttl_seconds=settings.REDIS_MEMORY_TTL_SECONDS,
            key_prefix=settings.REDIS_MEMORY_PREFIX,
        )
    except Exception:
        _memory = None

    return _memory


