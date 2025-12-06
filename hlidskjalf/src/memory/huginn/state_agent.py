"""
Huginn State Agent - Perception of the Present

Handles L3 (Session) and L4 (Turn) state with:
- Local in-memory cache for zero-latency reads
- Redis persistence for durability
- NATS JetStream for event distribution
- Kafka for durable event logging
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis
from pydantic import BaseModel, Field

from src.norns.squad_schema import Topics

logger = logging.getLogger(__name__)


class LLMModelConfig(BaseModel):
    """Configuration for a single LLM purpose"""
    provider: str = "lmstudio"  # ollama, lmstudio, openai
    model: str = "mistralai/ministral-3-14b-reasoning"
    temperature: float = 0.7
    
    
class LLMConfiguration(BaseModel):
    """Runtime LLM configuration - different models for different purposes"""
    reasoning: LLMModelConfig = Field(default_factory=LLMModelConfig)
    tools: LLMModelConfig = Field(default_factory=lambda: LLMModelConfig(
        provider="lmstudio", model="mistralai/ministral-3-14b-reasoning", temperature=0.1
    ))
    subagents: LLMModelConfig = Field(default_factory=lambda: LLMModelConfig(
        provider="lmstudio", model="mistralai/ministral-3-14b-reasoning", temperature=0.5
    ))


class TurnEvent(BaseModel):
    """Event emitted on each turn/utterance"""
    session_id: str
    user_id: str | None = None
    utterance: str
    intent: str | None = None
    slots: dict[str, Any] = Field(default_factory=dict)
    workflow_step: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionState(BaseModel):
    """Current session state - what is happening right now"""
    session_id: str = ""
    user_id: str | None = None
    utterance: str = ""
    intent: str | None = None
    slots: dict[str, Any] = Field(default_factory=dict)
    workflow_step: str | None = None
    flags: dict[str, bool] = Field(default_factory=dict)
    regulatory_constraints: list[str] = Field(default_factory=list)
    llm_config: LLMConfiguration = Field(default_factory=LLMConfiguration)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def is_empty(self) -> bool:
        return not self.session_id


class HuginnStateAgent:
    """
    Huginn perceives what is happening right now.
    
    Implements the Reactive Blackboard pattern:
    - State updates arrive via NATS events
    - Local cache is updated immediately
    - Redis provides persistence
    - Kafka records durable event log
    
    No synchronous state fetches in the hot path.
    """
    
    def __init__(
        self,
        redis_url: Any = "redis://redis:6379",  # Docker service name
        state_ttl_seconds: int = 3600,  # 1 hour
        nats_url: str | None = None,
        kafka_bootstrap: str | None = None,
    ):
        # Accept RedisDsn / AnyUrl instances as well as plain strings
        self.redis_url = str(redis_url)
        self.state_ttl = state_ttl_seconds
        self.nats_url = nats_url
        self.kafka_bootstrap = kafka_bootstrap
        
        # Local cache - zero latency reads
        self._state_cache: dict[str, SessionState] = {}
        
        # Connections (initialized lazily)
        self._redis: redis.Redis | None = None
        self._nats_client = None
        self._kafka_producer = None
        
    async def _get_redis(self) -> redis.Redis:
        """Lazy Redis connection"""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    async def _get_kafka(self):
        """Lazy Kafka producer"""
        if self._kafka_producer is None and self.kafka_bootstrap:
            try:
                from aiokafka import AIOKafkaProducer
                self._kafka_producer = AIOKafkaProducer(
                    bootstrap_servers=self.kafka_bootstrap
                )
                await self._kafka_producer.start()
            except ImportError:
                logger.warning("aiokafka not installed, Kafka events disabled")
        return self._kafka_producer
    
    def _redis_key(self, session_id: str) -> str:
        """Redis key for session state"""
        return f"huginn:session:{session_id}:state"
    
    async def on_turn_event(self, event: TurnEvent) -> None:
        """
        Handle incoming turn event - updates local cache and persists.
        
        This is the primary entry point for state updates.
        Called by NATS subscriber or directly.
        """
        session_id = event.session_id
        
        # Update local cache immediately
        state = SessionState(
            session_id=session_id,
            user_id=event.user_id,
            utterance=event.utterance,
            intent=event.intent,
            slots=event.slots,
            workflow_step=event.workflow_step,
            last_updated=event.timestamp,
        )
        self._state_cache[session_id] = state
        
        # Persist to Redis (async, non-blocking in practice)
        try:
            r = await self._get_redis()
            await r.setex(
                self._redis_key(session_id),
                self.state_ttl,
                state.model_dump_json()
            )
        except Exception as e:
            logger.error(f"Failed to persist state to Redis: {e}")
        
        # Emit to Kafka for durability
        try:
            producer = await self._get_kafka()
            if producer:
                await producer.send_and_wait(
                    "huginn.turn",
                    event.model_dump_json().encode()
                )
        except Exception as e:
            logger.error(f"Failed to emit to Kafka: {e}")
        
        logger.debug(f"Huginn perceived turn for session {session_id}")
    
    async def observe_turn(
        self,
        session_id: str,
        user_id: str | None = None,
        utterance: str = "",
        intent: str | None = None,
        slots: dict[str, Any] | None = None,
        workflow_step: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionState:
        """
        Public async helper used by agents to record perception for a session.
        Wraps on_turn_event with optional parameters and returns updated state.
        """
        event = TurnEvent(
            session_id=session_id,
            user_id=user_id,
            utterance=utterance,
            intent=intent,
            slots=slots or {},
            workflow_step=workflow_step,
            metadata=metadata or {},
        )
        await self.on_turn_event(event)
        return self._state_cache.get(session_id, SessionState(session_id=session_id))
    
    def perceive(self, session_id: str) -> SessionState:
        """
        What is happening right now?
        
        Zero-latency local cache lookup.
        This is the hot-path read - no I/O.
        """
        return self._state_cache.get(session_id, SessionState())
    
    async def perceive_with_fallback(self, session_id: str) -> SessionState:
        """
        Perceive with Redis fallback if not in local cache.
        
        Use this for cold starts or cross-process scenarios.
        Not recommended for hot path.
        """
        # Try local cache first
        if session_id in self._state_cache:
            return self._state_cache[session_id]
        
        # Fall back to Redis
        try:
            r = await self._get_redis()
            data = await r.get(self._redis_key(session_id))
            if data:
                state = SessionState.model_validate_json(data)
                self._state_cache[session_id] = state
                return state
        except Exception as e:
            logger.error(f"Failed to load state from Redis: {e}")
        
        return SessionState()
    
    async def update_intent(self, session_id: str, intent: str) -> None:
        """Update parsed intent for session"""
        state = self.perceive(session_id)
        if not state.is_empty():
            state.intent = intent
            state.last_updated = datetime.now(timezone.utc)
            self._state_cache[session_id] = state
            
            r = await self._get_redis()
            await r.setex(
                self._redis_key(session_id),
                self.state_ttl,
                state.model_dump_json()
            )
    
    async def set_flag(self, session_id: str, flag: str, value: bool) -> None:
        """Set a routing/state flag"""
        state = self.perceive(session_id)
        if not state.is_empty():
            state.flags[flag] = value
            state.last_updated = datetime.now(timezone.utc)
            self._state_cache[session_id] = state
            
            r = await self._get_redis()
            await r.setex(
                self._redis_key(session_id),
                self.state_ttl,
                state.model_dump_json()
            )
    
    async def add_regulatory_constraint(self, session_id: str, constraint: str) -> None:
        """Add a regulatory constraint to the session"""
        state = self.perceive(session_id)
        if not state.is_empty() and constraint not in state.regulatory_constraints:
            state.regulatory_constraints.append(constraint)
            state.last_updated = datetime.now(timezone.utc)
            self._state_cache[session_id] = state
            
            r = await self._get_redis()
            await r.setex(
                self._redis_key(session_id),
                self.state_ttl,
                state.model_dump_json()
            )
    
    async def clear_session(self, session_id: str) -> None:
        """Clear session state (on session end)"""
        self._state_cache.pop(session_id, None)
        
        try:
            r = await self._get_redis()
            await r.delete(self._redis_key(session_id))
        except Exception as e:
            logger.error(f"Failed to clear session from Redis: {e}")
    
    async def update_llm_config(
        self, 
        session_id: str, 
        config: LLMConfiguration
    ) -> LLMConfiguration:
        """
        Update LLM configuration for a session.
        
        This allows runtime switching of models without restart.
        """
        state = await self.perceive_with_fallback(session_id)
        
        # If no state exists yet, create one
        if state.is_empty():
            state = SessionState(session_id=session_id)
        
        state.llm_config = config
        state.last_updated = datetime.now(timezone.utc)
        self._state_cache[session_id] = state
        
        # Persist to Redis
        try:
            r = await self._get_redis()
            await r.setex(
                self._redis_key(session_id),
                self.state_ttl,
                state.model_dump_json()
            )
            logger.info(f"Updated LLM config for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to persist LLM config to Redis: {e}")
        
        # Emit event for any listeners
        try:
            producer = await self._get_kafka()
            if producer:
                event_data = {
                    "type": "llm.config.changed",
                    "session_id": session_id,
                    "config": config.model_dump(),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await producer.send_and_wait(
                    Topics.LLM_CONFIG,
                    json.dumps(event_data).encode()
                )
        except Exception as e:
            logger.error(f"Failed to emit LLM config event: {e}")
        
        return config
    
    async def get_llm_config(self, session_id: str) -> LLMConfiguration:
        """Get current LLM configuration for a session"""
        state = await self.perceive_with_fallback(session_id)
        return state.llm_config if not state.is_empty() else LLMConfiguration()
    
    def get_active_sessions(self) -> list[str]:
        """Get list of active session IDs in local cache"""
        return list(self._state_cache.keys())
    
    async def close(self) -> None:
        """Clean up connections"""
        if self._redis:
            await self._redis.close()
        if self._kafka_producer:
            await self._kafka_producer.stop()

