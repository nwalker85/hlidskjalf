"""
Huginn NATS Subscriber - Real-time event ingestion

Subscribes to NATS JetStream for turn-level events
and updates the HuginnStateAgent's local cache.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable

from pydantic import ValidationError

from src.memory.huginn.state_agent import HuginnStateAgent, TurnEvent

logger = logging.getLogger(__name__)


class HuginnNATSSubscriber:
    """
    NATS JetStream subscriber for Huginn events.
    
    Subscribes to:
    - huginn.turn.* - Turn-level state updates
    - huginn.session.* - Session-level events
    
    Updates the HuginnStateAgent's local cache on each event.
    """
    
    def __init__(
        self,
        state_agent: HuginnStateAgent,
        nats_url: str = "nats://nats:4222",  # Docker service name
        stream_name: str = "HUGINN",
    ):
        self.state_agent = state_agent
        self.nats_url = nats_url
        self.stream_name = stream_name
        
        self._nc = None
        self._js = None
        self._subscriptions: list = []
        self._running = False
    
    async def connect(self) -> None:
        """Connect to NATS and set up JetStream"""
        try:
            import nats
            from nats.js.api import StreamConfig, RetentionPolicy
            
            self._nc = await nats.connect(self.nats_url)
            self._js = self._nc.jetstream()
            
            # Create or update stream
            try:
                await self._js.add_stream(
                    config=StreamConfig(
                        name=self.stream_name,
                        subjects=["huginn.>"],
                        retention=RetentionPolicy.LIMITS,
                        max_age=3600,  # 1 hour retention
                    )
                )
                logger.info(f"Created/updated NATS stream: {self.stream_name}")
            except Exception as e:
                logger.debug(f"Stream may already exist: {e}")
            
            logger.info(f"Connected to NATS at {self.nats_url}")
            
        except ImportError:
            logger.warning("nats-py not installed, NATS subscriber disabled")
            return
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise
    
    async def subscribe(self) -> None:
        """Subscribe to Huginn event subjects"""
        if not self._js:
            logger.warning("NATS not connected, cannot subscribe")
            return
        
        try:
            # Subscribe to turn events
            turn_sub = await self._js.subscribe(
                "huginn.turn.*",
                cb=self._handle_turn_event,
                durable="huginn-state-agent",
            )
            self._subscriptions.append(turn_sub)
            logger.info("Subscribed to huginn.turn.*")
            
            # Subscribe to session events
            session_sub = await self._js.subscribe(
                "huginn.session.*",
                cb=self._handle_session_event,
                durable="huginn-session-agent",
            )
            self._subscriptions.append(session_sub)
            logger.info("Subscribed to huginn.session.*")
            
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
            raise
    
    async def _handle_turn_event(self, msg) -> None:
        """Handle incoming turn event"""
        try:
            data = json.loads(msg.data.decode())
            event = TurnEvent.model_validate(data)
            await self.state_agent.on_turn_event(event)
            await msg.ack()
            
        except ValidationError as e:
            logger.error(f"Invalid turn event: {e}")
            await msg.nak()
        except Exception as e:
            logger.error(f"Error handling turn event: {e}")
            await msg.nak()
    
    async def _handle_session_event(self, msg) -> None:
        """Handle session-level events (start, end, etc.)"""
        try:
            data = json.loads(msg.data.decode())
            event_type = data.get("type")
            session_id = data.get("session_id")
            
            if event_type == "session.end" and session_id:
                await self.state_agent.clear_session(session_id)
                logger.debug(f"Cleared session {session_id}")
            
            await msg.ack()
            
        except Exception as e:
            logger.error(f"Error handling session event: {e}")
            await msg.nak()
    
    async def publish_turn(self, event: TurnEvent) -> None:
        """Publish a turn event to NATS"""
        if not self._js:
            logger.warning("NATS not connected, cannot publish")
            return
        
        try:
            await self._js.publish(
                f"huginn.turn.{event.session_id}",
                event.model_dump_json().encode()
            )
        except Exception as e:
            logger.error(f"Failed to publish turn event: {e}")
    
    async def run(self) -> None:
        """Run the subscriber (blocking)"""
        await self.connect()
        await self.subscribe()
        
        self._running = True
        logger.info("Huginn NATS subscriber running")
        
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.close()
    
    async def close(self) -> None:
        """Clean up subscriptions and connection"""
        self._running = False
        
        for sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception:
                pass
        self._subscriptions.clear()
        
        if self._nc:
            await self._nc.close()
            self._nc = None
        
        logger.info("Huginn NATS subscriber closed")

