from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List

from src.api.llm_config import get_available_providers
from src.core.config import get_settings
from src.memory.events.kafka_producer import KafkaEventProducer
from src.norns.squad_schema import Topics

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMModelWatcher:
    """
    Periodically checks installed LLM models (currently via Ollama)
    and emits `llm.providers.updated` events whenever the inventory changes.
    """

    def __init__(
        self,
        poll_interval_seconds: int = 60,
        kafka_bootstrap: str | None = None,
    ) -> None:
        self._poll_interval = poll_interval_seconds
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_snapshot: Dict[str, List[str]] = {}
        self._producer = KafkaEventProducer(
            bootstrap_servers=kafka_bootstrap or settings.KAFKA_BOOTSTRAP,
            client_id="llm-model-watcher",
        )

    async def start(self) -> None:
        if self._task:
            return

        connected = await self._producer.connect()
        if not connected:
            logger.warning("LLMModelWatcher could not connect to Kafka; events will be skipped.")

        self._running = True
        self._task = asyncio.create_task(self._run(), name="llm-model-watcher")
        logger.info("LLMModelWatcher started with interval %ss", self._poll_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._producer.close()
        logger.info("LLMModelWatcher stopped")

    async def _run(self) -> None:
        while self._running:
            try:
                await self._poll_once()
            except Exception as exc:
                logger.error("LLMModelWatcher poll failed: %s", exc)
            await asyncio.sleep(self._poll_interval)

    async def _poll_once(self) -> None:
        providers = await get_available_providers()
        snapshot: Dict[str, List[str]] = {
            provider.id: sorted(provider.models) for provider in providers
        }

        if snapshot != self._last_snapshot:
            self._last_snapshot = snapshot
            await self._emit_event(providers)

    async def _emit_event(self, providers) -> None:
        event = {
            "type": "llm.providers.updated",
            "providers": [provider.model_dump() for provider in providers],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self._producer.is_connected:
            await self._producer.publish_to_topic(
                Topics.LLM_CONFIG,
                event,
                key="providers",
            )
            logger.info(
                "Published llm.providers.updated event with %d providers",
                len(providers),
            )
        else:
            logger.warning(
                "Skipping llm.providers.updated event because Kafka connection is unavailable"
            )

