from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any, Dict, Optional

from src.norns.squad_schema import Topics

logger = logging.getLogger(__name__)


class LLMConfigRegistry:
    """
    Lightweight cache fed by llm.config.changed events.
    
    Runs a background Kafka consumer (when available) and records the latest
    configuration per session. Exposes `get_config` for synchronous callers.
    """

    def __init__(self, bootstrap_servers: str | None = None):
        self.bootstrap = bootstrap_servers
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._running = False

    def start(self) -> None:
        """Start the background consumer thread (idempotent)."""
        if self._running or not self.bootstrap:
            return

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._running = True

    def stop(self) -> None:
        """Stop the background thread."""
        self._stop.set()

    def _run(self) -> None:
        """Run the asyncio consumer loop."""
        try:
            asyncio.run(self._consume())
        except Exception as exc:
            logger.warning("LLM config registry consumer stopped: %s", exc)
            self._running = False

    async def _consume(self) -> None:
        """Consume Kafka events and update cache."""
        try:
            from aiokafka import AIOKafkaConsumer
        except ImportError:
            logger.warning("aiokafka not installed, LLM config registry disabled")
            self._running = False
            return

        consumer = AIOKafkaConsumer(
            Topics.LLM_CONFIG,
            bootstrap_servers=self.bootstrap,
            auto_offset_reset="latest",
            group_id="llm-config-runtime",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )

        await consumer.start()
        logger.info("LLM config registry consuming from %s", Topics.LLM_CONFIG)
        try:
            async for message in consumer:
                event = message.value
                self.ingest_event(event)
                if self._stop.is_set():
                    break
        finally:
            await consumer.stop()
            self._running = False

    def ingest_event(self, event: dict[str, Any]) -> None:
        """Record an incoming event (used by consumer and tests)."""
        session_id = event.get("session_id")
        config = event.get("config")
        if session_id and isinstance(config, dict):
            self._configs[session_id] = config

    def get_config(self, session_id: str) -> Optional[dict[str, Any]]:
        """Return cached config for session, if any."""
        return self._configs.get(session_id)

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Return a shallow copy of cached configs (for diagnostics)."""
        return dict(self._configs)


_registry: Optional[LLMConfigRegistry] = None


def get_llm_config_registry(bootstrap_servers: str | None) -> LLMConfigRegistry:
    global _registry
    if _registry is None:
        _registry = LLMConfigRegistry(bootstrap_servers)
    return _registry


