"""
Cognitive Norns - The Norns with full Raven cognitive architecture

Integrates:
- Huginn (state perception)
- Frigg (context/persona)
- Muninn (long-term memory)
- Hel (memory governance)
- Mímir (domain intelligence)
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.core.config import get_settings

logger = logging.getLogger(__name__)


class CognitiveNorns:
    """
    The Norns with full cognitive architecture.
    
    This class integrates all components of the Raven memory system
    and provides a unified interface for the agent.
    
    Uses Ollama for local LLM operations (embeddings, reasoning)
    to reduce costs and enable offline operation.
    """
    
    def __init__(
        self,
        dossier_path: Path | str | None = None,
        redis_url: str | None = None,
        database_url: str | None = None,
        neo4j_uri: str | None = None,
        neo4j_auth: tuple[str, str] | None = None,
        nats_url: str | None = None,
        kafka_bootstrap: str | None = None,
        ollama_base_url: str | None = None,
        use_ollama: bool = True,
    ):
        import os
        settings = get_settings()
        
        # Configuration
        self.dossier_path = Path(dossier_path) if dossier_path else Path("hlidskjalf/dossiers/ravenhelm")
        # Default to Docker service names for containerized deployment
        self.redis_url = redis_url or settings.REDIS_URL or "redis://redis:6379"
        self.database_url = database_url or str(settings.DATABASE_URL or "")
        self.neo4j_uri = neo4j_uri or os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
        self.neo4j_auth = neo4j_auth or (
            os.environ.get("NEO4J_USER", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", "ravenhelm")
        )
        self.nats_url = nats_url or os.environ.get("NATS_URL", "nats://nats:4222")
        self.kafka_bootstrap = kafka_bootstrap or os.environ.get("KAFKA_BOOTSTRAP", "redpanda:9092")
        self.ollama_base_url = ollama_base_url or os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
        self.use_ollama = use_ollama
        
        # Components (initialized lazily)
        self._huginn = None
        self._frigg = None
        self._muninn = None
        self._hel = None
        self._mimir_loader = None
        self._mimir_engine = None
        self._event_producer = None
        self._ollama = None
        
        # The underlying LangGraph agent
        self._graph = None
        
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all cognitive components"""
        if self._initialized:
            return
        
        logger.info("Initializing Cognitive Norns...")
        
        # Initialize Ollama (Local LLM)
        if self.use_ollama:
            try:
                from src.memory.ollama_provider import OllamaProvider
                self._ollama = OllamaProvider(
                    base_url=self.ollama_base_url,
                    embedding_model="nomic-embed-text",
                    chat_model="llama3.1:8b",
                )
                if await self._ollama.initialize():
                    logger.info("✓ Ollama initialized (local LLM)")
                else:
                    logger.warning("Ollama models not ready, falling back to cloud")
                    self._ollama = None
            except Exception as e:
                logger.warning(f"Ollama not available: {e}")
                self._ollama = None
        
        # Initialize Huginn (State)
        from src.memory.huginn import HuginnStateAgent
        self._huginn = HuginnStateAgent(
            redis_url=self.redis_url,
            nats_url=self.nats_url,
            kafka_bootstrap=self.kafka_bootstrap,
        )
        logger.info("✓ Huginn initialized")
        
        # Initialize Muninn (Memory) with Ollama embeddings
        from src.memory.muninn import MuninnStore
        self._muninn = MuninnStore(
            database_url=self.database_url if self.database_url else None,
            ollama_base_url=self.ollama_base_url,
            use_ollama=self.use_ollama and self._ollama is not None,
        )
        logger.info("✓ Muninn initialized")
        
        # Initialize Hel (Governance)
        from src.memory.hel import HelWeightEngine
        self._hel = HelWeightEngine()
        logger.info("✓ Hel initialized")
        
        # Initialize Frigg (Context)
        from src.memory.frigg import FriggContextAgent
        self._frigg = FriggContextAgent(
            store=None,  # Will use PostgresStore when available
            muninn=self._muninn,
            kafka_bootstrap=self.kafka_bootstrap,
        )
        logger.info("✓ Frigg initialized")
        
        # Initialize Mímir (Domain)
        if self.dossier_path.exists():
            from src.memory.mimir import MimirDossierLoader, MimirTripletEngine
            self._mimir_loader = MimirDossierLoader(self.dossier_path)
            
            try:
                dossier = self._mimir_loader.load_wisdom()
                self._mimir_engine = MimirTripletEngine(dossier)
                
                # Validate dossier
                errors = self._mimir_loader.validate()
                if errors:
                    logger.warning(f"Dossier validation warnings: {errors}")
                
                logger.info(f"✓ Mímir initialized with dossier: {dossier.name}")
            except Exception as e:
                logger.error(f"Failed to load dossier: {e}")
        else:
            logger.warning(f"Dossier path not found: {self.dossier_path}")
        
        # Initialize Event Fabric
        from src.memory.events import NATSEventProducer
        self._event_producer = NATSEventProducer(nats_url=self.nats_url)
        try:
            await self._event_producer.connect()
            logger.info("✓ Event fabric connected")
        except Exception as e:
            logger.warning(f"Event fabric not connected: {e}")
        
        # Initialize memory tools
        from src.norns.memory_tools import init_memory_tools
        init_memory_tools(
            huginn=self._huginn,
            frigg=self._frigg,
            muninn=self._muninn,
            hel=self._hel,
            mimir=self._mimir_engine,
        )
        logger.info("✓ Memory tools initialized")
        
        self._initialized = True
        logger.info("Cognitive Norns ready")
    
    async def process_turn(
        self,
        session_id: str,
        user_id: str,
        message: str,
    ) -> dict[str, Any]:
        """
        Process a single turn with full cognitive context.
        
        1. Huginn perceives the turn
        2. Frigg builds persona context
        3. Mímir determines valid actions
        4. Agent processes with enriched context
        5. Muninn remembers the interaction
        """
        if not self._initialized:
            await self.initialize()
        
        # 1. Huginn perceives
        from src.memory.huginn import TurnEvent
        turn_event = TurnEvent(
            session_id=session_id,
            user_id=user_id,
            utterance=message,
        )
        await self._huginn.on_turn_event(turn_event)
        state = self._huginn.perceive(session_id)
        
        # 2. Frigg builds context
        from src.memory.frigg import StateEvent
        state_event = StateEvent(
            session_id=session_id,
            user_id=user_id,
            intent=state.intent,
            slots=state.slots,
        )
        persona = await self._frigg.on_state_event(state_event)
        
        # 3. Mímir determines valid actions
        valid_actions = []
        if self._mimir_engine and persona.current_role:
            triplets = self._mimir_engine.consult(
                persona.current_role,
                {"session": state.model_dump(), "persona": persona.model_dump()},
            )
            valid_actions = [t.name for t in triplets]
        
        # 4. Build enriched context for agent
        context = {
            "state": state.model_dump(),
            "persona": persona.to_context_dict(),
            "available_actions": valid_actions,
        }
        
        # 5. Invoke the underlying agent (if configured)
        response = await self._invoke_agent(message, context)
        
        # 6. Muninn remembers
        from src.memory.muninn import MemoryFragment, MemoryType
        episode = MemoryFragment(
            type=MemoryType.EPISODIC,
            content=f"User: {message}\nAssistant: {response.get('content', '')}",
            domain="conversation",
            topic=state.intent,
            user_id=user_id,
            session_id=session_id,
        )
        await self._muninn.remember(episode)
        
        return response
    
    async def _invoke_agent(
        self,
        message: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke the underlying LangGraph agent"""
        if self._graph is None:
            # Initialize the graph lazily
            from src.norns.agent import create_norns_graph
            self._graph = create_norns_graph()
        
        # Build the input with context
        from src.norns.agent import NornState
        
        result = await self._graph.ainvoke({
            "messages": [HumanMessage(content=message)],
            "context": context,
        })
        
        # Extract response
        if result.get("messages"):
            last_msg = result["messages"][-1]
            return {
                "content": last_msg.content if hasattr(last_msg, "content") else str(last_msg),
                "context": context,
            }
        
        return {"content": "", "context": context}
    
    # ==========================================================================
    # Public API
    # ==========================================================================
    
    def perceive(self, session_id: str):
        """Huginn: What is happening right now?"""
        if not self._huginn:
            return None
        return self._huginn.perceive(session_id)
    
    def divine(self, session_id: str):
        """Frigg: What does she know of this user's fate?"""
        if not self._frigg:
            return None
        return self._frigg.divine(session_id)
    
    async def recall(self, query: str, k: int = 5):
        """Muninn: Search long-term memory"""
        if not self._muninn:
            return []
        return await self._muninn.recall(query, k=k)
    
    def consult(self, role_id: str, context: dict[str, Any] | None = None):
        """Mímir: What actions are valid for this role?"""
        if not self._mimir_engine:
            return []
        return self._mimir_engine.consult(role_id, context or {})
    
    def reinforce(self, memory, importance: float = 1.0):
        """Hel: Strengthen a memory"""
        if not self._hel:
            return 0.0
        return self._hel.reinforce(memory, importance)
    
    # ==========================================================================
    # Lifecycle
    # ==========================================================================
    
    async def close(self) -> None:
        """Clean up all resources"""
        if self._huginn:
            await self._huginn.close()
        if self._muninn:
            await self._muninn.close()
        if self._event_producer:
            await self._event_producer.close()
        
        self._initialized = False
        logger.info("Cognitive Norns closed")


# =============================================================================
# Factory function
# =============================================================================

async def create_cognitive_norns(
    dossier_path: Path | str | None = None,
    **kwargs,
) -> CognitiveNorns:
    """
    Create and initialize a CognitiveNorns instance.
    
    Usage:
        norns = await create_cognitive_norns()
        response = await norns.process_turn(session_id, user_id, message)
    """
    norns = CognitiveNorns(dossier_path=dossier_path, **kwargs)
    await norns.initialize()
    return norns

