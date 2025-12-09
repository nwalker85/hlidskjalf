"""
Ollama Provider - Local LLM integration for Raven cognitive architecture

Provides:
- Local embeddings (nomic-embed-text, mxbai-embed-large)
- Local chat models (llama3.1, mistral, etc.)
- Cost-free operation for development
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class OllamaConfig(BaseModel):
    """Configuration for Ollama provider"""
    base_url: str = "http://ollama:11434"  # Docker service name
    embedding_model: str = "nomic-embed-text"  # Fast, good quality
    chat_model: str = "llama3.1:8b"
    timeout: float = 120.0  # Longer timeout for first model load


class OllamaEmbeddings:
    """
    Ollama embeddings provider for Muninn.
    
    Recommended models:
    - nomic-embed-text: Fast, 768 dimensions, good for retrieval
    - mxbai-embed-large: Higher quality, 1024 dimensions
    - all-minilm: Very fast, 384 dimensions
    """
    
    def __init__(
        self,
        base_url: str = "http://ollama:11434",
        model: str = "nomic-embed-text",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._dimension: int | None = None
        # Don't cache client - create fresh for each request to handle event loop changes
    
    async def ensure_model(self) -> bool:
        """Ensure the embedding model is available, pull if needed"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Check if model exists
            try:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "").split(":")[0] for m in models]
                    
                    if self.model.split(":")[0] in model_names:
                        logger.info(f"Ollama model {self.model} is available")
                        return True
            except Exception as e:
                logger.warning(f"Failed to check Ollama models: {e}")
            
            # Pull the model
            logger.info(f"Pulling Ollama model: {self.model}")
            try:
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": self.model, "stream": False},
                    timeout=600.0,  # 10 minutes for large models
                )
                return response.status_code == 200
            except Exception as e:
                logger.error(f"Failed to pull model {self.model}: {e}")
                return False
    
    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query text"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                
                if response.status_code == 200:
                    embedding = response.json().get("embedding", [])
                    if not self._dimension:
                        self._dimension = len(embedding)
                    return embedding
                else:
                    logger.error(f"Ollama embedding failed: {response.status_code}")
                    return []
                    
            except Exception as e:
                logger.error(f"Ollama embedding error: {e}")
                return []
    
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple documents"""
        embeddings = []
        for text in texts:
            emb = await self.embed_query(text)
            embeddings.append(emb)
        return embeddings
    
    # Sync versions for LangChain compatibility
    def embed_query_sync(self, text: str) -> list[float]:
        """Synchronous embed for LangChain compatibility"""
        return asyncio.get_event_loop().run_until_complete(self.embed_query(text))
    
    def embed_documents_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous embed documents for LangChain compatibility"""
        return asyncio.get_event_loop().run_until_complete(self.embed_documents(texts))
    
    @property
    def dimension(self) -> int:
        """Get embedding dimension (query first to determine)"""
        return self._dimension or 768  # Default for nomic-embed-text
    
    async def close(self) -> None:
        """No-op - clients are not cached"""
        pass


class OllamaChat:
    """
    Ollama chat provider for cognitive agents.
    
    Recommended models:
    - llama3.1:8b: Good balance of speed and quality
    - mistral:7b: Fast, good for simple tasks
    - llama3.1:70b: High quality, slower (needs GPU)
    """
    
    def __init__(
        self,
        base_url: str = "http://ollama:11434",
        model: str = "llama3.1:8b",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
    
    async def ensure_model(self) -> bool:
        """Ensure the chat model is available"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    
                    # Check for exact match or base model
                    model_base = self.model.split(":")[0]
                    for name in model_names:
                        if name == self.model or name.startswith(model_base):
                            return True
            except Exception:
                pass
            
            # Pull the model
            logger.info(f"Pulling Ollama model: {self.model}")
            try:
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": self.model, "stream": False},
                    timeout=600.0,
                )
                return response.status_code == 200
            except Exception as e:
                logger.error(f"Failed to pull model {self.model}: {e}")
                return False
    
    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Send a chat request to Ollama.
        
        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
            system: Optional system prompt
            temperature: Sampling temperature
            
        Returns:
            Assistant response text
        """
        # Build messages with optional system prompt
        formatted_messages = []
        if system:
            formatted_messages.append({"role": "system", "content": system})
        formatted_messages.extend(messages)
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": formatted_messages,
                        "stream": False,
                        "options": {"temperature": temperature},
                    },
                )
                
                if response.status_code == 200:
                    return response.json().get("message", {}).get("content", "")
                else:
                    logger.error(f"Ollama chat failed: {response.status_code}")
                    return ""
                    
            except Exception as e:
                logger.error(f"Ollama chat error: {e}")
                return ""
    
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        """Simple generation without chat format"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": system or "",
                        "stream": False,
                        "options": {"temperature": temperature},
                    },
                )
                
                if response.status_code == 200:
                    return response.json().get("response", "")
                return ""
                
            except Exception as e:
                logger.error(f"Ollama generate error: {e}")
                return ""
    
    async def close(self) -> None:
        """No-op - clients are not cached"""
        pass


class OllamaProvider:
    """
    Combined Ollama provider for the cognitive architecture.
    
    Usage:
        provider = OllamaProvider()
        await provider.initialize()
        
        # Embeddings for Muninn
        embedding = await provider.embed("some text")
        
        # Chat for cognitive reasoning
        response = await provider.chat([{"role": "user", "content": "..."}])
    """
    
    def __init__(
        self,
        base_url: str = "http://ollama:11434",
        embedding_model: str = "nomic-embed-text",
        chat_model: str = "llama3.1:8b",
    ):
        self.base_url = base_url
        self.embeddings = OllamaEmbeddings(base_url, embedding_model)
        self.chat_client = OllamaChat(base_url, chat_model)
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize and ensure models are available"""
        logger.info(f"Initializing Ollama provider at {self.base_url}")
        
        # Ensure embedding model
        emb_ok = await self.embeddings.ensure_model()
        if not emb_ok:
            logger.warning("Embedding model not available")
        
        # Ensure chat model
        chat_ok = await self.chat_client.ensure_model()
        if not chat_ok:
            logger.warning("Chat model not available")
        
        self._initialized = emb_ok or chat_ok
        return self._initialized
    
    async def embed(self, text: str) -> list[float]:
        """Get embedding for text"""
        return await self.embeddings.embed_query(text)
    
    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for multiple texts"""
        return await self.embeddings.embed_documents(texts)
    
    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
    ) -> str:
        """Chat completion"""
        return await self.chat_client.chat(messages, system)
    
    async def generate(self, prompt: str, system: str | None = None) -> str:
        """Simple text generation"""
        return await self.chat_client.generate(prompt, system)
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized
    
    async def close(self) -> None:
        await self.embeddings.close()
        await self.chat_client.close()


# =============================================================================
# LangChain Compatibility Wrapper
# =============================================================================

class OllamaEmbeddingsLC:
    """LangChain-compatible Ollama embeddings wrapper"""
    
    def __init__(self, base_url: str = "http://ollama:11434", model: str = "nomic-embed-text"):
        self._ollama = OllamaEmbeddings(base_url, model)
        self._loop = None
    
    def _get_loop(self):
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop
    
    def embed_query(self, text: str) -> list[float]:
        """Sync embed query for LangChain"""
        loop = self._get_loop()
        return loop.run_until_complete(self._ollama.embed_query(text))
    
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Sync embed documents for LangChain"""
        loop = self._get_loop()
        return loop.run_until_complete(self._ollama.embed_documents(texts))
    
    async def aembed_query(self, text: str) -> list[float]:
        """Async embed query"""
        return await self._ollama.embed_query(text)
    
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Async embed documents"""
        return await self._ollama.embed_documents(texts)

