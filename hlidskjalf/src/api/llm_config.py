"""
LLM Configuration API - Provider and model configuration management

Provides endpoints for:
- Managing LLM providers (OpenAI, Anthropic, custom servers)
- Configuring models for different interaction types
- Validating provider connectivity
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from typing import List
from uuid import UUID

from src.core.config import get_settings
from src.services.llm_providers import LLMProviderService
from src.services.llm_config import LLMConfigService
from src.models.llm_config import (
    ProviderCreate,
    ProviderUpdate,
    ProviderResponse,
    ModelCreate,
    ModelResponse,
    InteractionConfigUpdate,
    InteractionConfigResponse,
    GlobalConfigResponse,
    InteractionType,
)

router = APIRouter()
settings = get_settings()

# Create async engine
engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """Dependency to get database session"""
    async with async_session_maker() as session:
        yield session


# =============================================================================
# Provider Management Endpoints
# =============================================================================

@router.get(
    "/llm/providers",
    response_model=List[ProviderResponse],
    tags=["LLM Configuration"],
    summary="List all LLM providers"
)
async def list_providers(
    enabled_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of all configured LLM providers.
    
    Args:
        enabled_only: If true, only return enabled providers
    """
    service = LLMProviderService(db)
    providers = await service.list_providers(enabled_only=enabled_only)
    
    return [
        ProviderResponse(
            id=str(p.id),
            name=p.name,
            provider_type=p.provider_type.value,
            api_base_url=p.api_base_url,
            enabled=p.enabled,
            validated_at=p.validated_at,
            created_at=p.created_at,
            updated_at=p.updated_at,
            models=[m.model_name for m in p.models]
        )
        for p in providers
    ]


@router.post(
    "/llm/providers",
    response_model=ProviderResponse,
    tags=["LLM Configuration"],
    summary="Add a new LLM provider"
)
async def add_provider(
    provider_data: ProviderCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Add a new LLM provider.
    
    For OpenAI/Anthropic, only name and API key are required.
    For custom servers, name, api_base_url, and optional API key are required.
    
    The custom server will be validated before being added.
    """
    service = LLMProviderService(db)
    
    try:
        provider = await service.add_provider(provider_data)
        return ProviderResponse(
            id=str(provider.id),
            name=provider.name,
            provider_type=provider.provider_type.value,
            api_base_url=provider.api_base_url,
            enabled=provider.enabled,
            validated_at=provider.validated_at,
            created_at=provider.created_at,
            updated_at=provider.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add provider: {str(e)}")


@router.put(
    "/llm/providers/{provider_id}",
    response_model=ProviderResponse,
    tags=["LLM Configuration"],
    summary="Update a provider"
)
async def update_provider(
    provider_id: UUID,
    update_data: ProviderUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing provider's configuration"""
    service = LLMProviderService(db)
    
    try:
        provider = await service.update_provider(provider_id, update_data)
        return ProviderResponse(
            id=str(provider.id),
            name=provider.name,
            provider_type=provider.provider_type.value,
            api_base_url=provider.api_base_url,
            enabled=provider.enabled,
            validated_at=provider.validated_at,
            created_at=provider.created_at,
            updated_at=provider.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update provider: {str(e)}")


@router.delete(
    "/llm/providers/{provider_id}",
    tags=["LLM Configuration"],
    summary="Remove a provider"
)
async def remove_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Disable a provider (soft delete)"""
    service = LLMProviderService(db)
    
    success = await service.remove_provider(provider_id)
    if not success:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    return {"success": True, "message": "Provider disabled"}


@router.post(
    "/llm/providers/{provider_id}/validate",
    tags=["LLM Configuration"],
    summary="Validate a provider"
)
async def validate_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate a provider's configuration by testing connectivity.
    
    For custom servers, tests the /v1/models endpoint.
    For OpenAI/Anthropic, checks if API key is present.
    """
    service = LLMProviderService(db)
    
    try:
        is_valid = await service.validate_provider(provider_id)
        return {
            "provider_id": str(provider_id),
            "valid": is_valid,
            "message": "Provider is valid" if is_valid else "Provider validation failed"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")


@router.get(
    "/llm/providers/{provider_id}/models",
    response_model=List[ModelResponse],
    tags=["LLM Configuration"],
    summary="Get models for a provider"
)
async def get_provider_models(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get available models for a provider.
    
    Fetches from provider API if not already cached in database.
    """
    service = LLMProviderService(db)
    
    try:
        models = await service.get_available_models(provider_id)
        return [
            ModelResponse(
                id=str(m.id),
                provider_id=str(m.provider_id),
                model_name=m.model_name,
                supports_tools=m.supports_tools,
                supports_embeddings=m.supports_embeddings,
                context_window=m.context_window,
                cost_per_1k_input_tokens=float(m.cost_per_1k_input_tokens) if m.cost_per_1k_input_tokens else None,
                cost_per_1k_output_tokens=float(m.cost_per_1k_output_tokens) if m.cost_per_1k_output_tokens else None
            )
            for m in models
        ]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {str(e)}")


@router.post(
    "/llm/providers/{provider_id}/sync-models",
    tags=["LLM Configuration"],
    summary="Sync models from provider API"
)
async def sync_provider_models(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch and sync all available models from the provider's API.
    
    This will update the database with the latest models available,
    including newly released models (e.g., GPT-4.5, new Claude versions).
    """
    service = LLMProviderService(db)
    
    try:
        provider = await service.get_provider(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        
        # Fetch fresh models from API (will add new ones, existing ones remain)
        await service._fetch_and_store_models(provider)
        await db.commit()
        await db.refresh(provider)
        
        return {
            "success": True,
            "model_count": len(provider.models),
            "models": [m.model_name for m in provider.models]
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to sync models: {str(e)}")


@router.post(
    "/llm/providers/{provider_id}/models",
    response_model=ModelResponse,
    tags=["LLM Configuration"],
    summary="Manually add a model to a provider"
)
async def add_model(
    provider_id: UUID,
    model_data: ModelCreate,
    db: AsyncSession = Depends(get_db)
):
    """Manually add a model to a provider (useful for custom servers)"""
    service = LLMProviderService(db)
    
    try:
        model = await service.add_model(provider_id, model_data)
        return ModelResponse(
            id=str(model.id),
            provider_id=str(model.provider_id),
            model_name=model.model_name,
            supports_tools=model.supports_tools,
            supports_embeddings=model.supports_embeddings,
            context_window=model.context_window,
            cost_per_1k_input_tokens=float(model.cost_per_1k_input_tokens) if model.cost_per_1k_input_tokens else None,
            cost_per_1k_output_tokens=float(model.cost_per_1k_output_tokens) if model.cost_per_1k_output_tokens else None
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add model: {str(e)}")


# =============================================================================
# Configuration Management Endpoints
# =============================================================================

@router.get(
    "/llm/config",
    response_model=GlobalConfigResponse,
    tags=["LLM Configuration"],
    summary="Get global LLM configuration"
)
async def get_global_config(db: AsyncSession = Depends(get_db)):
    """
    Get current global configuration for all interaction types.
    
    Returns the configured model for reasoning, tools, subagents, planning, and embeddings.
    """
    service = LLMConfigService(db)
    
    try:
        configs = await service.get_global_config()
        
        # Build response - ensure all interaction types have config
        response_dict = {}
        for interaction_type in InteractionType:
            config = configs.get(interaction_type.value)
            if config:
                response_dict[interaction_type.value] = InteractionConfigResponse(
                    interaction_type=interaction_type.value,
                    provider_id=str(config.provider_id),
                    model_name=config.model_name,
                    temperature=float(config.temperature),
                    max_tokens=config.max_tokens,
                    updated_at=config.updated_at
                )
        
        if len(response_dict) != len(InteractionType):
            raise HTTPException(
                status_code=500,
                detail="Incomplete configuration - not all interaction types are configured"
            )
        
        return GlobalConfigResponse(**response_dict)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch config: {str(e)}")


@router.put(
    "/llm/config/{interaction_type}",
    response_model=InteractionConfigResponse,
    tags=["LLM Configuration"],
    summary="Update configuration for an interaction type"
)
async def update_interaction_config(
    interaction_type: InteractionType,
    config_update: InteractionConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update the model configuration for a specific interaction type.
    
    Interaction types:
    - reasoning: Main supervisor thinking and decision making
    - tools: Tool calling and result parsing
    - subagents: Specialized agent tasks
    - planning: TODO generation and planning
    - embeddings: Vector embeddings for RAG
    """
    service = LLMConfigService(db)
    
    try:
        config = await service.update_interaction_config(interaction_type, config_update)
        return InteractionConfigResponse(
            interaction_type=interaction_type.value,
            provider_id=str(config.provider_id),
            model_name=config.model_name,
            temperature=float(config.temperature),
            max_tokens=config.max_tokens,
            updated_at=config.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@router.get(
    "/llm/config/summary",
    tags=["LLM Configuration"],
    summary="Get configuration summary"
)
async def get_config_summary(db: AsyncSession = Depends(get_db)):
    """
    Get a human-readable summary of current configuration.
    
    Useful for debugging and displaying in UI.
    """
    service = LLMConfigService(db)
    
    try:
        summary = await service.get_config_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch summary: {str(e)}")


@router.get(
    "/llm/config/validate",
    tags=["LLM Configuration"],
    summary="Validate all configurations"
)
async def validate_all_configs(db: AsyncSession = Depends(get_db)):
    """
    Validate that all interaction types have valid, working configurations.
    
    Returns validation status for each interaction type.
    """
    service = LLMConfigService(db)
    
    try:
        results = await service.validate_all_configs()
        return {
            "valid": all(results.values()),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")
