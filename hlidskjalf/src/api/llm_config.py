"""
LLM Configuration API - Runtime model switching

Allows dynamic switching of LLM providers and models without restart.
Configuration is stored in Huginn session state and read by the agent on each turn.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import logging

from src.memory.huginn.state_agent import (
    HuginnStateAgent,
    LLMConfiguration,
    LLMModelConfig,
)
from src.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

# Singleton Huginn instance for config storage
_huginn: Optional[HuginnStateAgent] = None


async def get_huginn() -> HuginnStateAgent:
    """Get or create Huginn state agent"""
    global _huginn
    if _huginn is None:
        _huginn = HuginnStateAgent(
            redis_url=settings.REDIS_URL,
            state_ttl_seconds=86400,  # 24 hours for config
        )
    return _huginn


# =============================================================================
# Request/Response Models
# =============================================================================

class LLMModelConfigRequest(BaseModel):
    """Request model for a single LLM configuration"""
    provider: str = Field(default="ollama", description="Provider: ollama, lmstudio, openai")
    model: str = Field(default="mistral-nemo:latest", description="Model identifier")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature for generation")


class LLMConfigurationRequest(BaseModel):
    """Request model for full LLM configuration"""
    reasoning: LLMModelConfigRequest = Field(
        default_factory=LLMModelConfigRequest,
        description="Model for main agent reasoning"
    )
    tools: LLMModelConfigRequest = Field(
        default_factory=lambda: LLMModelConfigRequest(temperature=0.1),
        description="Model for tool execution"
    )
    subagents: LLMModelConfigRequest = Field(
        default_factory=lambda: LLMModelConfigRequest(temperature=0.5),
        description="Model for subagent tasks"
    )


class LLMConfigurationResponse(BaseModel):
    """Response model with current LLM configuration"""
    session_id: str
    reasoning: LLMModelConfigRequest
    tools: LLMModelConfigRequest
    subagents: LLMModelConfigRequest
    
    
class AvailableProvider(BaseModel):
    """Information about an available LLM provider"""
    id: str
    name: str
    available: bool
    models: list[str]
    default_model: str


class AvailableProvidersResponse(BaseModel):
    """Response listing all available providers"""
    providers: list[AvailableProvider]


# =============================================================================
# Endpoints
# =============================================================================

@router.get(
    "/llm/providers",
    response_model=AvailableProvidersResponse,
    tags=["LLM Config"],
    summary="List available LLM providers"
)
async def list_providers():
    """
    List all available LLM providers and their models.
    
    This returns static configuration - actual availability 
    should be checked via health endpoints.
    """
    providers = [
        AvailableProvider(
            id="ollama",
            name="Ollama",
            available=True,  # Assume available, health check will verify
            models=[
                "mistral-nemo:latest",
                "llama3.1:8b",
                "codellama:latest",
                "deepseek-coder:latest",
            ],
            default_model="mistral-nemo:latest",
        ),
        AvailableProvider(
            id="lmstudio",
            name="LM Studio",
            available=True,
            models=["local-model"],  # LM Studio serves whatever is loaded
            default_model="local-model",
        ),
        AvailableProvider(
            id="openai",
            name="OpenAI",
            available=bool(settings.OPENAI_API_KEY),
            models=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
            default_model="gpt-4o",
        ),
    ]
    
    return AvailableProvidersResponse(providers=providers)


@router.get(
    "/llm/config/{session_id}",
    response_model=LLMConfigurationResponse,
    tags=["LLM Config"],
    summary="Get LLM configuration for session"
)
async def get_llm_config(session_id: str):
    """
    Get the current LLM configuration for a session.
    
    If no configuration exists, returns the default configuration.
    """
    huginn = await get_huginn()
    config = await huginn.get_llm_config(session_id)
    
    return LLMConfigurationResponse(
        session_id=session_id,
        reasoning=LLMModelConfigRequest(
            provider=config.reasoning.provider,
            model=config.reasoning.model,
            temperature=config.reasoning.temperature,
        ),
        tools=LLMModelConfigRequest(
            provider=config.tools.provider,
            model=config.tools.model,
            temperature=config.tools.temperature,
        ),
        subagents=LLMModelConfigRequest(
            provider=config.subagents.provider,
            model=config.subagents.model,
            temperature=config.subagents.temperature,
        ),
    )


@router.post(
    "/llm/config/{session_id}",
    response_model=LLMConfigurationResponse,
    tags=["LLM Config"],
    summary="Update LLM configuration for session"
)
async def update_llm_config(session_id: str, request: LLMConfigurationRequest):
    """
    Update the LLM configuration for a session.
    
    This takes effect immediately - the next agent invocation
    will use the new configuration.
    
    **Example:**
    ```json
    {
        "reasoning": {
            "provider": "ollama",
            "model": "mistral-nemo:latest",
            "temperature": 0.7
        },
        "tools": {
            "provider": "ollama", 
            "model": "mistral-nemo:latest",
            "temperature": 0.1
        },
        "subagents": {
            "provider": "ollama",
            "model": "mistral-nemo:latest", 
            "temperature": 0.5
        }
    }
    ```
    """
    huginn = await get_huginn()
    
    # Convert request to internal config model
    config = LLMConfiguration(
        reasoning=LLMModelConfig(
            provider=request.reasoning.provider,
            model=request.reasoning.model,
            temperature=request.reasoning.temperature,
        ),
        tools=LLMModelConfig(
            provider=request.tools.provider,
            model=request.tools.model,
            temperature=request.tools.temperature,
        ),
        subagents=LLMModelConfig(
            provider=request.subagents.provider,
            model=request.subagents.model,
            temperature=request.subagents.temperature,
        ),
    )
    
    # Update and persist
    updated_config = await huginn.update_llm_config(session_id, config)
    
    logger.info(f"Updated LLM config for session {session_id}: {updated_config}")
    
    return LLMConfigurationResponse(
        session_id=session_id,
        reasoning=LLMModelConfigRequest(
            provider=updated_config.reasoning.provider,
            model=updated_config.reasoning.model,
            temperature=updated_config.reasoning.temperature,
        ),
        tools=LLMModelConfigRequest(
            provider=updated_config.tools.provider,
            model=updated_config.tools.model,
            temperature=updated_config.tools.temperature,
        ),
        subagents=LLMModelConfigRequest(
            provider=updated_config.subagents.provider,
            model=updated_config.subagents.model,
            temperature=updated_config.subagents.temperature,
        ),
    )


@router.delete(
    "/llm/config/{session_id}",
    tags=["LLM Config"],
    summary="Reset LLM configuration to defaults"
)
async def reset_llm_config(session_id: str):
    """
    Reset the LLM configuration for a session to defaults.
    """
    huginn = await get_huginn()
    
    # Set default config
    default_config = LLMConfiguration()
    await huginn.update_llm_config(session_id, default_config)
    
    return {"status": "reset", "session_id": session_id}
