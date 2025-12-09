from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.core.config import get_settings
from src.services.llm_providers import LLMProviderService
from src.memory.events.kafka_producer import KafkaEventProducer
from src.norns.squad_schema import Topics

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMModelWatcher:
    """
    Periodically checks configured LLM providers from the database
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
        
        # Database connection for provider queries
        self._engine = create_async_engine(
            str(settings.DATABASE_URL),
            echo=False,
            pool_size=2,
            max_overflow=0,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
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
        await self._engine.dispose()
        logger.info("LLMModelWatcher stopped")

    async def _run(self) -> None:
        while self._running:
            try:
                await self._poll_once()
            except Exception as exc:
                logger.error("LLMModelWatcher poll failed: %s", exc)
            await asyncio.sleep(self._poll_interval)

    async def _poll_once(self) -> None:
        async with self._session_factory() as session:
            provider_service = LLMProviderService(db_session=session)
            providers = await provider_service.list_providers(enabled_only=True)
            
            # Build snapshot of provider IDs to model names
            snapshot: Dict[str, List[str]] = {
                str(provider.id): sorted([m.model_name for m in provider.models])
                for provider in providers
            }

            if snapshot != self._last_snapshot:
                self._last_snapshot = snapshot
                await self._emit_event(providers)

    async def _emit_event(self, providers) -> None:
        # Convert SQLAlchemy models to dicts for serialization
        provider_dicts = [
            {
                "id": str(provider.id),
                "name": provider.name,
                "provider_type": provider.provider_type.value,
                "enabled": provider.enabled,
                "models": [m.model_name for m in provider.models],
            }
            for provider in providers
        ]
        
        event = {
            "type": "llm.providers.updated",
            "providers": provider_dicts,
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

