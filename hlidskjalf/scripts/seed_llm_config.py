#!/usr/bin/env python3
"""
Seed script for LLM configuration system.

Creates default OpenAI provider and sensible global configuration.
Run after database migration 002_llm_providers_config.sql.

Usage:
    # With OpenAI API key
    export OPENAI_API_KEY="sk-..."
    python -m scripts.seed_llm_config

    # Without API key (will create disabled provider)
    python -m scripts.seed_llm_config
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from structlog import get_logger

from src.core.config import get_settings
from src.services.llm_providers import LLMProviderService
from src.services.llm_config import LLMConfigService
from src.models.llm_config import ProviderType, InteractionType, ProviderCreate

logger = get_logger(__name__)


async def seed_llm_config():
    """Seed the database with default LLM configuration."""
    settings = get_settings()
    
    # Create async engine
    engine = create_async_engine(
        str(settings.DATABASE_URL),
        echo=False,
    )
    
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_factory() as session:
        provider_service = LLMProviderService(db_session=session)
        config_service = LLMConfigService(db_session=session)
        
        # Check if OpenAI API key is available
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        
        if not openai_api_key:
            logger.warning(
                "No OPENAI_API_KEY found in environment. "
                "Provider will be created but disabled. "
                "Add API key via UI or API to enable."
            )
        
        # 1. Create OpenAI provider
        logger.info("Creating default OpenAI provider...")
        try:
            provider_data = ProviderCreate(
                name="OpenAI",
                provider_type=ProviderType.OPENAI,
                api_key=openai_api_key if openai_api_key else None,
            )
            openai_provider = await provider_service.add_provider(provider_data)
            logger.info(f"✓ Created OpenAI provider: {openai_provider.id}")
        except Exception as e:
            logger.error(f"Failed to create OpenAI provider: {e}")
            # Check if it already exists
            providers = await provider_service.list_providers()
            openai_provider = next(
                (p for p in providers if p.name == "OpenAI"), None
            )
            if not openai_provider:
                raise
            logger.info(f"Using existing OpenAI provider: {openai_provider.id}")
        
        # 2. Validate provider if API key is present
        if openai_api_key:
            logger.info("Validating OpenAI provider...")
            try:
                is_valid = await provider_service.validate_provider(openai_provider.id)
                if is_valid:
                    logger.info("✓ OpenAI provider validated successfully")
                else:
                    logger.warning("⚠ OpenAI provider validation failed")
            except Exception as e:
                logger.error(f"Provider validation error: {e}")
        
        # 3. Fetch available models
        logger.info("Fetching available models...")
        try:
            models = await provider_service.get_available_models(openai_provider.id)
            logger.info(f"✓ Found {len(models)} models: {', '.join(models[:5])}...")
        except Exception as e:
            logger.warning(f"Could not fetch models: {e}")
            models = []
        
        # 4. Configure global defaults
        logger.info("Configuring global defaults...")
        
        # Default configuration map
        default_configs = {
            InteractionType.REASONING: {
                "model": "gpt-4o",
                "temperature": 0.7,
                "description": "Main supervisor thinking and decision making",
            },
            InteractionType.TOOLS: {
                "model": "gpt-4o-mini",
                "temperature": 0.1,
                "description": "Tool calling and result parsing",
            },
            InteractionType.SUBAGENTS: {
                "model": "gpt-4o-mini",
                "temperature": 0.5,
                "description": "Specialized agent tasks",
            },
            InteractionType.PLANNING: {
                "model": "gpt-4o",
                "temperature": 0.2,
                "description": "TODO generation and planning",
            },
            InteractionType.EMBEDDINGS: {
                "model": "text-embedding-3-small",
                "temperature": 0.0,
                "description": "Vector embeddings for RAG",
            },
        }
        
        for interaction_type, config in default_configs.items():
            try:
                await config_service.update_interaction_config(
                    interaction_type=interaction_type,
                    provider_id=openai_provider.id,
                    model_name=config["model"],
                    temperature=config["temperature"],
                )
                logger.info(
                    f"✓ Configured {interaction_type.value}: "
                    f"{config['model']} (temp={config['temperature']})"
                )
            except Exception as e:
                logger.error(
                    f"Failed to configure {interaction_type.value}: {e}"
                )
        
        # 5. Validate configuration
        logger.info("\nValidating configuration...")
        try:
            global_config = await config_service.get_global_config()
            logger.info("\n=== Current Configuration ===")
            for interaction_type, model_config in global_config.items():
                logger.info(
                    f"{interaction_type.value:12} → "
                    f"{model_config.provider_name}/{model_config.model_name} "
                    f"(temp={model_config.temperature})"
                )
            logger.info("=" * 50)
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
        
        # Commit all changes
        await session.commit()
        
        logger.info("\n✓ Seed complete!")
        logger.info("\nNext steps:")
        logger.info("1. Start Hliðskjálf: docker-compose up hlidskjalf")
        logger.info("2. Open dashboard: https://hlidskjalf.ravenhelm.test:8443")
        logger.info("3. Click 'LLM Settings' to review configuration")
        
        if not openai_api_key:
            logger.info("\n⚠ Remember to add your OpenAI API key via the UI!")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_llm_config())
