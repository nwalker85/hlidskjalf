"""
NATS Event Producer - Hot-path event emission

Uses NATS JetStream for ultra-low-latency event delivery.
"""

from __future__ import annotations

import logging
from typing import Any

from src.memory.events.schemas import RavenEvent, EventType

logger = logging.getLogger(__name__)


class NATSEventProducer:
    """
    NATS JetStream producer for hot-path events.
    
    Used for:
    - Turn-level state updates (huginn.turn.*)
    - Real-time notifications
    - Agent coordination
    """
    
    def __init__(
        self,
        nats_url: str = "nats://nats:4222",  # Docker service name
        stream_name: str = "RAVEN",
    ):
        self.nats_url = nats_url
        self.stream_name = stream_name
        
        self._nc = None
        self._js = None
        self._connected = False
    
    async def connect(self) -> bool:
        """Connect to NATS and set up JetStream"""
        try:
            import nats
            from nats.js.api import StreamConfig, RetentionPolicy
            
            self._nc = await nats.connect(self.nats_url)
            self._js = self._nc.jetstream()
            
            # Create stream for all Raven events
            try:
                await self._js.add_stream(
                    config=StreamConfig(
                        name=self.stream_name,
                        subjects=[
                            "huginn.>",
                            "frigg.>",
                            "muninn.>",
                            "hel.>",
                            "mimir.>",
                        ],
                        retention=RetentionPolicy.LIMITS,
                        max_age=3600 * 4,  # 4 hour retention
                    )
                )
                logger.info(f"Created NATS stream: {self.stream_name}")
            except Exception:
                # Stream may already exist
                pass
            
            self._connected = True
            logger.info(f"Connected to NATS at {self.nats_url}")
            return True
            
        except ImportError:
            logger.warning("nats-py not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            return False
    
    async def publish(self, event: RavenEvent) -> bool:
        """
        Publish an event to NATS.
        
        Subject is derived from event_type (e.g., "huginn.turn").
        """
        if not self._js:
            logger.warning("NATS not connected")
            return False
        
        subject = event.event_type.value
        
        # Add session_id to subject if present
        if event.session_id:
            subject = f"{subject}.{event.session_id}"
        
        try:
            ack = await self._js.publish(
                subject,
                event.model_dump_json().encode(),
            )
            logger.debug(f"Published to {subject}: seq={ack.seq}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish to NATS: {e}")
            return False
    
    async def publish_raw(
        self,
        subject: str,
        data: dict[str, Any],
    ) -> bool:
        """Publish raw data to a specific subject"""
        if not self._js:
            return False
        
        try:
            import json
            await self._js.publish(
                subject,
                json.dumps(data).encode(),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to publish raw to NATS: {e}")
            return False
    
    async def close(self) -> None:
        """Close NATS connection"""
        if self._nc:
            await self._nc.close()
            self._nc = None
            self._js = None
            self._connected = False
            logger.info("NATS connection closed")
    
    @property
    def is_connected(self) -> bool:
        return self._connected

