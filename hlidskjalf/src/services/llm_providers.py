"""
LLM Provider Service - Manages LLM providers and model discovery.

Handles:
- Adding/removing/updating providers (OpenAI, Anthropic, custom servers)
- Validating custom OpenAI-compatible servers
- Fetching available models from provider APIs
- Encrypting API keys via LocalStack Secrets Manager
"""

import httpx
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.llm_config import (
    LLMProvider,
    LLMProviderModel,
    ProviderType,
    ProviderCreate,
    ProviderUpdate,
    ModelCreate,
)
from src.core.secrets import get_secrets_client

logger = logging.getLogger(__name__)


class LLMProviderService:
    """Service for managing LLM providers and models"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.secrets_client = get_secrets_client()

    # =========================================================================
    # Provider Management
    # =========================================================================

    async def list_providers(self, enabled_only: bool = False) -> List[LLMProvider]:
        """
        List all configured providers.
        
        Args:
            enabled_only: If True, only return enabled providers
            
        Returns:
            List of LLMProvider instances with models loaded
        """
        query = select(LLMProvider).options(selectinload(LLMProvider.models))
        
        if enabled_only:
            query = query.where(LLMProvider.enabled == True)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_provider(self, provider_id: UUID) -> Optional[LLMProvider]:
        """
        Get a provider by ID with models loaded.
        
        Args:
            provider_id: Provider UUID
            
        Returns:
            LLMProvider instance or None
        """
        query = (
            select(LLMProvider)
            .options(selectinload(LLMProvider.models))
            .where(LLMProvider.id == provider_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_provider_by_name(self, name: str) -> Optional[LLMProvider]:
        """Get a provider by name"""
        query = select(LLMProvider).where(LLMProvider.name == name)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def add_provider(self, provider_data: ProviderCreate) -> LLMProvider:
        """
        Add a new LLM provider.
        
        Args:
            provider_data: Provider creation data
            
        Returns:
            Created LLMProvider instance
            
        Raises:
            ValueError: If provider name already exists or validation fails
        """
        # Check for duplicate name
        existing = await self.get_provider_by_name(provider_data.name)
        if existing:
            raise ValueError(f"Provider with name '{provider_data.name}' already exists")

        # Validate custom server if applicable
        if provider_data.provider_type == ProviderType.CUSTOM:
            if not provider_data.api_base_url:
                raise ValueError("api_base_url is required for custom providers")
            
            # Validate the server
            is_valid = await self._validate_custom_server(
                provider_data.api_base_url,
                provider_data.api_key
            )
            if not is_valid:
                raise ValueError(f"Custom server at {provider_data.api_base_url} failed validation")

        # Store API key in LocalStack Secrets Manager
        api_key_secret_path = None
        if provider_data.api_key:
            api_key_secret_path = f"ravenhelm/dev/llm/{provider_data.name.lower().replace(' ', '_')}"
            await self.secrets_client.store_secret(api_key_secret_path, provider_data.api_key)
            logger.info(f"Stored API key for provider '{provider_data.name}' at {api_key_secret_path}")

        # Create provider
        provider = LLMProvider(
            name=provider_data.name,
            provider_type=provider_data.provider_type,
            api_base_url=provider_data.api_base_url,
            api_key_secret_path=api_key_secret_path,
            enabled=True,
            validated_at=datetime.utcnow() if provider_data.provider_type == ProviderType.CUSTOM else None,
        )

        self.db.add(provider)
        await self.db.flush()  # Get the ID
        await self.db.refresh(provider)

        # Fetch and add models
        try:
            await self._fetch_and_store_models(provider)
        except Exception as e:
            logger.warning(f"Failed to fetch models for provider '{provider.name}': {e}")
            # Continue anyway - models can be added manually

        await self.db.commit()
        logger.info(f"Added provider '{provider.name}' ({provider.provider_type})")
        
        return provider

    async def update_provider(
        self,
        provider_id: UUID,
        update_data: ProviderUpdate
    ) -> LLMProvider:
        """
        Update a provider's configuration.
        
        Args:
            provider_id: Provider UUID
            update_data: Fields to update
            
        Returns:
            Updated LLMProvider instance
            
        Raises:
            ValueError: If provider not found or validation fails
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")

        # Update fields
        if update_data.name is not None:
            # Check for duplicate name
            existing = await self.get_provider_by_name(update_data.name)
            if existing and existing.id != provider_id:
                raise ValueError(f"Provider with name '{update_data.name}' already exists")
            provider.name = update_data.name

        if update_data.api_base_url is not None:
            provider.api_base_url = update_data.api_base_url

        if update_data.enabled is not None:
            provider.enabled = update_data.enabled

        # Update API key if provided
        if update_data.api_key is not None:
            if provider.api_key_secret_path:
                # Update existing secret
                await self.secrets_client.store_secret(
                    provider.api_key_secret_path,
                    update_data.api_key
                )
            else:
                # Create new secret
                secret_path = f"ravenhelm/dev/llm/{provider.name.lower().replace(' ', '_')}"
                await self.secrets_client.store_secret(secret_path, update_data.api_key)
                provider.api_key_secret_path = secret_path

        provider.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(provider)

        logger.info(f"Updated provider '{provider.name}'")
        return provider

    async def remove_provider(self, provider_id: UUID) -> bool:
        """
        Remove a provider (soft delete by disabling).
        
        Args:
            provider_id: Provider UUID
            
        Returns:
            True if provider was disabled, False if not found
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            return False

        provider.enabled = False
        provider.updated_at = datetime.utcnow()
        await self.db.commit()

        logger.info(f"Disabled provider '{provider.name}'")
        return True

    # =========================================================================
    # Validation
    # =========================================================================

    async def validate_provider(self, provider_id: UUID) -> bool:
        """
        Validate a provider's configuration by testing API connectivity.
        
        Args:
            provider_id: Provider UUID
            
        Returns:
            True if validation successful, False otherwise
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")

        if provider.provider_type == ProviderType.CUSTOM:
            # Get API key from secrets
            api_key = None
            if provider.api_key_secret_path:
                api_key = self.secrets_client.get_secret(provider.api_key_secret_path)

            is_valid = await self._validate_custom_server(
                provider.api_base_url,
                api_key
            )
            
            if is_valid:
                provider.validated_at = datetime.utcnow()
                await self.db.commit()
            
            return is_valid
        else:
            # For OpenAI/Anthropic, just check if API key exists
            if provider.api_key_secret_path:
                api_key = self.secrets_client.get_secret(provider.api_key_secret_path)
                return api_key is not None
            return False

    async def _validate_custom_server(
        self,
        base_url: str,
        api_key: Optional[str] = None
    ) -> bool:
        """
        Validate a custom OpenAI-compatible server.
        
        Checks that the /v1/models endpoint exists and returns valid data.
        
        Args:
            base_url: Base URL of the server
            api_key: Optional API key
            
        Returns:
            True if server is valid, False otherwise
        """
        try:
            # Ensure base_url doesn't end with /
            base_url = base_url.rstrip("/")
            
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{base_url}/v1/models",
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.warning(f"Custom server validation failed: HTTP {response.status_code}")
                    return False

                # Check response has expected structure
                data = response.json()
                if not isinstance(data, dict) or "data" not in data:
                    logger.warning(f"Custom server returned invalid response structure")
                    return False

                models = data.get("data", [])
                if not isinstance(models, list) or len(models) == 0:
                    logger.warning(f"Custom server returned no models")
                    return False

                logger.info(f"Custom server validation successful: {len(models)} models found")
                return True

        except Exception as e:
            logger.error(f"Custom server validation error: {e}")
            return False

    # =========================================================================
    # Model Management
    # =========================================================================

    async def get_available_models(self, provider_id: UUID) -> List[LLMProviderModel]:
        """
        Get models for a provider, fetching from API if needed.
        
        Args:
            provider_id: Provider UUID
            
        Returns:
            List of LLMProviderModel instances
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")

        # If we have models in DB, return them
        if provider.models:
            return provider.models

        # Otherwise, try to fetch from provider
        await self._fetch_and_store_models(provider)
        await self.db.refresh(provider)
        
        return provider.models

    async def add_model(
        self,
        provider_id: UUID,
        model_data: ModelCreate
    ) -> LLMProviderModel:
        """
        Manually add a model to a provider.
        
        Args:
            provider_id: Provider UUID
            model_data: Model creation data
            
        Returns:
            Created LLMProviderModel instance
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")

        model = LLMProviderModel(
            provider_id=provider_id,
            model_name=model_data.model_name,
            supports_tools=model_data.supports_tools,
            supports_embeddings=model_data.supports_embeddings,
            context_window=model_data.context_window,
            cost_per_1k_input_tokens=model_data.cost_per_1k_input_tokens,
            cost_per_1k_output_tokens=model_data.cost_per_1k_output_tokens,
        )

        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)

        logger.info(f"Added model '{model.model_name}' to provider '{provider.name}'")
        return model

    async def _fetch_and_store_models(self, provider: LLMProvider) -> None:
        """
        Fetch models from provider API and store in database.
        
        Args:
            provider: LLMProvider instance
        """
        if provider.provider_type == ProviderType.OPENAI:
            models_data = await self._fetch_openai_models(provider)
        elif provider.provider_type == ProviderType.ANTHROPIC:
            models_data = self._get_anthropic_models()
        elif provider.provider_type == ProviderType.CUSTOM:
            models_data = await self._fetch_custom_server_models(provider)
        else:
            logger.warning(f"Unknown provider type: {provider.provider_type}")
            return

        # Store models (upsert to handle duplicates)
        from sqlalchemy.dialects.postgresql import insert
        
        for model_data in models_data:
            stmt = insert(LLMProviderModel).values(
                provider_id=provider.id,
                **model_data
            )
            # On conflict, update the model metadata
            stmt = stmt.on_conflict_do_update(
                index_elements=['provider_id', 'model_name'],
                set_={
                    'supports_tools': stmt.excluded.supports_tools,
                    'supports_embeddings': stmt.excluded.supports_embeddings,
                    'context_window': stmt.excluded.context_window,
                    'cost_per_1k_input_tokens': stmt.excluded.cost_per_1k_input_tokens,
                    'cost_per_1k_output_tokens': stmt.excluded.cost_per_1k_output_tokens,
                    'updated_at': datetime.utcnow(),
                }
            )
            await self.db.execute(stmt)

        await self.db.flush()
        logger.info(f"Synced {len(models_data)} models for provider '{provider.name}'")

    async def _fetch_openai_models(self, provider: LLMProvider) -> List[Dict[str, Any]]:
        """Fetch models from OpenAI API"""
        try:
            api_key = None
            if provider.api_key_secret_path:
                api_key = self.secrets_client.get_secret(provider.api_key_secret_path)

            if not api_key:
                logger.warning("No API key available for OpenAI provider")
                return []

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                
                if response.status_code != 200:
                    logger.warning(f"OpenAI API returned {response.status_code}")
                    return []

                data = response.json()
                models = []
                
                # Include all GPT and embedding models
                # Exclude: fine-tuned, deprecated, and non-LLM models
                excluded_prefixes = [
                    "dall-e", "tts", "whisper", "babbage", "davinci", "curie", "ada",
                    "text-davinci", "text-curie", "text-babbage", "text-ada",
                    "code-", "text-similarity", "text-search", "ft:"
                ]
                
                # Exclude specific model types that aren't for general chat/completion
                excluded_suffixes = [
                    "-transcribe", "-transcribe-diarize", "-tts", 
                    "-realtime-preview", "-audio-preview"
                ]
                
                for model_info in data.get("data", []):
                    model_id = model_info.get("id", "")
                    
                    # Skip excluded prefixes
                    if any(model_id.startswith(prefix) for prefix in excluded_prefixes):
                        continue
                    
                    # Skip excluded suffixes (specialized models)
                    if any(model_id.endswith(suffix) for suffix in excluded_suffixes):
                        continue
                    
                    # Skip if it's a fine-tuned model
                    if "ft-" in model_id or model_id.startswith("ft:"):
                        continue
                    
                    # Include all GPT models (including GPT-4.1, GPT-5, GPT-5.1, etc.) and embeddings
                    if model_id.startswith("gpt-") or model_id.startswith("text-embedding"):
                        is_embedding = "embedding" in model_id
                        is_search = "search" in model_id
                        
                        models.append({
                            "model_name": model_id,
                            "supports_tools": not is_embedding and not is_search,
                            "supports_embeddings": is_embedding,
                            "context_window": self._get_openai_context_window(model_id),
                            "cost_per_1k_input_tokens": self._get_openai_cost(model_id, "input"),
                            "cost_per_1k_output_tokens": self._get_openai_cost(model_id, "output"),
                        })
                
                logger.info(f"Fetched {len(models)} OpenAI models from API")
                return models

        except Exception as e:
            logger.error(f"Error fetching OpenAI models: {e}")
            return []

    def _get_anthropic_models(self) -> List[Dict[str, Any]]:
        """Get Anthropic models (hardcoded as they don't have a models API)"""
        return [
            {
                "model_name": "claude-3-5-sonnet-20241022",
                "supports_tools": True,
                "supports_embeddings": False,
                "context_window": 200000,
                "cost_per_1k_input_tokens": 0.003,
                "cost_per_1k_output_tokens": 0.015,
            },
            {
                "model_name": "claude-3-5-haiku-20241022",
                "supports_tools": True,
                "supports_embeddings": False,
                "context_window": 200000,
                "cost_per_1k_input_tokens": 0.001,
                "cost_per_1k_output_tokens": 0.005,
            },
            {
                "model_name": "claude-3-opus-20240229",
                "supports_tools": True,
                "supports_embeddings": False,
                "context_window": 200000,
                "cost_per_1k_input_tokens": 0.015,
                "cost_per_1k_output_tokens": 0.075,
            },
        ]

    async def _fetch_custom_server_models(self, provider: LLMProvider) -> List[Dict[str, Any]]:
        """Fetch models from custom OpenAI-compatible server"""
        try:
            api_key = None
            if provider.api_key_secret_path:
                api_key = self.secrets_client.get_secret(provider.api_key_secret_path)

            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            base_url = provider.api_base_url.rstrip("/")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{base_url}/v1/models",
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.warning(f"Custom server returned {response.status_code}")
                    return []

                data = response.json()
                models = []
                
                for model_info in data.get("data", []):
                    model_id = model_info.get("id", "")
                    if model_id:
                        models.append({
                            "model_name": model_id,
                            "supports_tools": True,  # Assume true for custom servers
                            "supports_embeddings": False,
                            "context_window": 4096,  # Default
                            "cost_per_1k_input_tokens": None,
                            "cost_per_1k_output_tokens": None,
                        })
                
                return models

        except Exception as e:
            logger.error(f"Error fetching custom server models: {e}")
            return []

    def _get_openai_context_window(self, model_id: str) -> int:
        """Get context window size for OpenAI model"""
        if "gpt-4o" in model_id:
            return 128000
        elif "gpt-4-turbo" in model_id:
            return 128000
        elif "gpt-4" in model_id:
            return 8192
        elif "gpt-3.5-turbo" in model_id:
            return 16385
        elif "embedding" in model_id:
            return 8191
        return 4096

    def _get_openai_cost(self, model_id: str, token_type: str) -> Optional[float]:
        """Get cost per 1K tokens for OpenAI model"""
        costs = {
            "gpt-4o": {"input": 0.0025, "output": 0.01},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            "text-embedding-3-large": {"input": 0.00013, "output": 0.0},
            "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
        }
        
        for model_key, cost_data in costs.items():
            if model_key in model_id:
                return cost_data.get(token_type)
        
        return None

