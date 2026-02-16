"""
LLM Configuration Service - Manages global LLM configuration and provides LLM instances.

This service:
- Manages global configuration for each interaction type (reasoning, tools, subagents, planning, embeddings)
- Provides factory methods to get configured LangChain LLM instances
- Handles user-specific overrides (optional)
"""

import logging
from typing import Optional, Dict, Any
from decimal import Decimal

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_anthropic import ChatAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.llm_config import (
    LLMGlobalConfig,
    LLMUserConfig,
    LLMProvider,
    LLMProviderModel,
    InteractionType,
    ProviderType,
    InteractionConfigUpdate,
)
from src.core.secrets import get_secrets_client

logger = logging.getLogger(__name__)


class LLMConfigService:
    """Service for managing LLM configuration and creating LLM instances"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.secrets_client = get_secrets_client()

    # =========================================================================
    # Configuration Management
    # =========================================================================

    async def get_global_config(self) -> Dict[str, LLMGlobalConfig]:
        """
        Get global configuration for all interaction types.
        
        Returns:
            Dict mapping interaction type to config
        """
        query = (
            select(LLMGlobalConfig)
            .options(selectinload(LLMGlobalConfig.provider))
        )
        result = await self.db.execute(query)
        configs = result.scalars().all()
        
        return {
            config.interaction_type.value: config
            for config in configs
        }

    async def get_config_for_interaction(
        self,
        interaction_type: InteractionType,
        user_id: Optional[str] = None
    ) -> Optional[LLMGlobalConfig]:
        """
        Get configuration for a specific interaction type.
        
        Checks user-specific override first, then falls back to global config.
        
        Args:
            interaction_type: Type of interaction
            user_id: Optional user ID for user-specific config
            
        Returns:
            LLMGlobalConfig or None
        """
        # Check for user override
        if user_id:
            user_config = await self._get_user_config(user_id, interaction_type)
            if user_config:
                # Convert user config to global config format
                return self._user_config_to_global(user_config)
        
        # Get global config
        query = (
            select(LLMGlobalConfig)
            .options(selectinload(LLMGlobalConfig.provider))
            .where(LLMGlobalConfig.interaction_type == interaction_type)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_interaction_config(
        self,
        interaction_type: InteractionType,
        config_update: InteractionConfigUpdate
    ) -> LLMGlobalConfig:
        """
        Update global configuration for an interaction type.
        
        Supports partial updates - only provided fields will be changed.
        
        Args:
            interaction_type: Type of interaction to configure
            config_update: New configuration values (all fields optional)
            
        Returns:
            Updated LLMGlobalConfig
            
        Raises:
            ValueError: If provider/model not found or invalid
        """
        # Get existing config first
        query = select(LLMGlobalConfig).where(
            LLMGlobalConfig.interaction_type == interaction_type
        )
        result = await self.db.execute(query)
        config = result.scalar_one_or_none()
        
        # If no config exists and no provider/model specified, can't create
        if not config and (not config_update.provider_id or not config_update.model_name):
            raise ValueError(
                "provider_id and model_name are required when creating a new configuration"
            )
        
        # If provider is being changed, model must also be provided (can't mix providers)
        if config_update.provider_id is not None and config_update.model_name is None:
            if config and config_update.provider_id != config.provider_id:
                raise ValueError(
                    "model_name is required when changing provider"
                )
        
        # Determine the provider_id and model_name to use for validation
        provider_id = config_update.provider_id or (config.provider_id if config else None)
        model_name = config_update.model_name or (config.model_name if config else None)
        
        # Only validate provider/model if either is being explicitly changed
        if config_update.provider_id is not None or config_update.model_name is not None:
            if provider_id and model_name:
                # Verify provider exists
                provider_query = select(LLMProvider).where(
                    LLMProvider.id == provider_id
                )
                provider_result = await self.db.execute(provider_query)
                provider = provider_result.scalar_one_or_none()
                
                if not provider:
                    raise ValueError(f"Provider {provider_id} not found")
                
                if not provider.enabled:
                    raise ValueError(f"Provider '{provider.name}' is disabled")

                # Verify model exists for this provider
                model_query = select(LLMProviderModel).where(
                    LLMProviderModel.provider_id == provider_id,
                    LLMProviderModel.model_name == model_name
                )
                model_result = await self.db.execute(model_query)
                model = model_result.scalar_one_or_none()
                
                if not model:
                    raise ValueError(
                        f"Model '{model_name}' not found for provider '{provider.name}'"
                    )

                # Check model capabilities
                if interaction_type == InteractionType.EMBEDDINGS and not model.supports_embeddings:
                    raise ValueError(
                        f"Model '{model_name}' does not support embeddings"
                    )
                
                if interaction_type != InteractionType.EMBEDDINGS and not model.supports_tools:
                    logger.warning(
                        f"Model '{model_name}' may not support tool calling"
                    )
        
        if config:
            # Update existing - only update provided fields
            if config_update.provider_id is not None:
                config.provider_id = config_update.provider_id
            if config_update.model_name is not None:
                config.model_name = config_update.model_name
            if config_update.temperature is not None:
                config.temperature = Decimal(str(config_update.temperature))
            if config_update.max_tokens is not None:
                config.max_tokens = config_update.max_tokens
        else:
            # Create new - use defaults for unspecified fields
            config = LLMGlobalConfig(
                interaction_type=interaction_type,
                provider_id=provider_id,
                model_name=model_name,
                temperature=Decimal(str(config_update.temperature or 0.7)),
                max_tokens=config_update.max_tokens
            )
            self.db.add(config)
        
        await self.db.commit()
        
        # Reload with provider relationship for logging
        query = (
            select(LLMGlobalConfig)
            .options(selectinload(LLMGlobalConfig.provider))
            .where(LLMGlobalConfig.interaction_type == interaction_type)
        )
        result = await self.db.execute(query)
        config = result.scalar_one()
        
        provider_name = config.provider.name if config.provider else config.provider_id
        logger.info(
            f"Updated {interaction_type.value} config: {provider_name}/{config.model_name}"
        )
        
        return config

    async def _get_user_config(
        self,
        user_id: str,
        interaction_type: InteractionType
    ) -> Optional[LLMUserConfig]:
        """Get user-specific configuration override"""
        query = (
            select(LLMUserConfig)
            .options(selectinload(LLMUserConfig.provider))
            .where(
                LLMUserConfig.user_id == user_id,
                LLMUserConfig.interaction_type == interaction_type
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    def _user_config_to_global(self, user_config: LLMUserConfig) -> LLMGlobalConfig:
        """Convert user config to global config format for compatibility"""
        # Create a pseudo-global config from user config
        config = LLMGlobalConfig(
            interaction_type=user_config.interaction_type,
            provider_id=user_config.provider_id,
            model_name=user_config.model_name,
            temperature=user_config.temperature,
            max_tokens=user_config.max_tokens
        )
        config.provider = user_config.provider
        return config

    # =========================================================================
    # LLM Factory Methods
    # =========================================================================

    async def get_llm_for_interaction(
        self,
        interaction_type: InteractionType,
        user_id: Optional[str] = None,
        **kwargs
    ):
        """
        Get a configured LangChain LLM instance for an interaction type.
        
        Args:
            interaction_type: Type of interaction (reasoning, tools, etc.)
            user_id: Optional user ID for user-specific config
            **kwargs: Additional LLM parameters to override config
            
        Returns:
            ChatOpenAI, ChatAnthropic, or other LangChain LLM instance
            
        Raises:
            ValueError: If no configuration exists for interaction type
        """
        config = await self.get_config_for_interaction(interaction_type, user_id)
        
        if not config:
            raise ValueError(
                f"No configuration found for interaction type '{interaction_type.value}'"
            )

        provider = config.provider
        
        # Get API key from secrets
        api_key = None
        if provider.api_key_secret_path:
            api_key = await self.secrets_client.get_secret(provider.api_key_secret_path)
        
        if not api_key:
            raise ValueError(
                f"No API key configured for provider '{provider.name}'"
            )

        # Build LLM parameters
        llm_params = {
            "model": config.model_name,
            "temperature": float(config.temperature),
        }
        
        if config.max_tokens:
            llm_params["max_tokens"] = config.max_tokens
        
        # Override with any provided kwargs
        llm_params.update(kwargs)

        # Create appropriate LLM instance
        if provider.provider_type == ProviderType.OPENAI:
            llm_params["api_key"] = api_key
            return ChatOpenAI(**llm_params)
        
        elif provider.provider_type == ProviderType.ANTHROPIC:
            llm_params["anthropic_api_key"] = api_key
            return ChatAnthropic(**llm_params)
        
        elif provider.provider_type == ProviderType.CUSTOM:
            # Custom OpenAI-compatible server
            llm_params["api_key"] = api_key
            llm_params["base_url"] = provider.api_base_url
            return ChatOpenAI(**llm_params)
        
        else:
            raise ValueError(f"Unsupported provider type: {provider.provider_type}")

    async def get_embeddings_model(
        self,
        user_id: Optional[str] = None,
        **kwargs
    ):
        """
        Get a configured embeddings model.
        
        Args:
            user_id: Optional user ID for user-specific config
            **kwargs: Additional parameters to override config
            
        Returns:
            OpenAIEmbeddings or other embeddings instance
            
        Raises:
            ValueError: If no embeddings configuration exists
        """
        config = await self.get_config_for_interaction(
            InteractionType.EMBEDDINGS,
            user_id
        )
        
        if not config:
            raise ValueError("No embeddings configuration found")

        provider = config.provider
        
        # Get API key
        api_key = None
        if provider.api_key_secret_path:
            api_key = await self.secrets_client.get_secret(provider.api_key_secret_path)
        
        if not api_key:
            raise ValueError(f"No API key configured for provider '{provider.name}'")

        # Build embeddings parameters
        embed_params = {
            "model": config.model_name,
        }
        embed_params.update(kwargs)

        # Create embeddings instance
        if provider.provider_type == ProviderType.OPENAI:
            embed_params["openai_api_key"] = api_key
            return OpenAIEmbeddings(**embed_params)
        
        elif provider.provider_type == ProviderType.CUSTOM:
            embed_params["openai_api_key"] = api_key
            embed_params["openai_api_base"] = provider.api_base_url
            return OpenAIEmbeddings(**embed_params)
        
        else:
            raise ValueError(
                f"Provider type '{provider.provider_type}' does not support embeddings"
            )

    async def get_llm_with_tools(
        self,
        interaction_type: InteractionType,
        tools: list,
        user_id: Optional[str] = None,
        **kwargs
    ):
        """
        Get an LLM instance with tools bound.
        
        Args:
            interaction_type: Type of interaction
            tools: List of tools to bind
            user_id: Optional user ID
            **kwargs: Additional LLM parameters
            
        Returns:
            LLM instance with tools bound
        """
        llm = await self.get_llm_for_interaction(interaction_type, user_id, **kwargs)
        return llm.bind_tools(tools)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def get_config_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        Get a summary of all configurations for display/debugging.
        
        Returns:
            Dict with configuration details for each interaction type
        """
        configs = await self.get_global_config()
        
        summary = {}
        for interaction_type, config in configs.items():
            summary[interaction_type] = {
                "provider": config.provider.name,
                "provider_type": config.provider.provider_type.value,
                "model": config.model_name,
                "temperature": float(config.temperature),
                "max_tokens": config.max_tokens,
                "enabled": config.provider.enabled,
            }
        
        return summary

    async def validate_all_configs(self) -> Dict[str, bool]:
        """
        Validate that all interaction types have valid configurations.
        
        Returns:
            Dict mapping interaction type to validation status
        """
        results = {}
        
        for interaction_type in InteractionType:
            try:
                config = await self.get_config_for_interaction(interaction_type)
                if config and config.provider.enabled:
                    # Try to create LLM instance
                    if interaction_type == InteractionType.EMBEDDINGS:
                        await self.get_embeddings_model()
                    else:
                        await self.get_llm_for_interaction(interaction_type)
                    results[interaction_type.value] = True
                else:
                    results[interaction_type.value] = False
            except Exception as e:
                logger.error(f"Validation failed for {interaction_type.value}: {e}")
                results[interaction_type.value] = False
        
        return results


# =============================================================================
# Singleton Instance Helper
# =============================================================================

_config_service: Optional[LLMConfigService] = None


async def get_llm_config_service(db_session: AsyncSession) -> LLMConfigService:
    """
    Get or create LLMConfigService instance.
    
    Note: This creates a new instance per request. For long-lived services,
    create and reuse a single instance.
    """
    return LLMConfigService(db_session)

