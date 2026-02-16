"""
SQLAlchemy models for LLM Provider and Configuration management.

These models support cloud LLM providers (OpenAI, Anthropic) and custom
OpenAI-compatible servers with granular configuration per interaction type.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

Base = declarative_base()


# =============================================================================
# Enums
# =============================================================================

class ProviderType(str, PyEnum):
    """LLM provider types"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


class InteractionType(str, PyEnum):
    """Types of interactions that can use different models"""
    REASONING = "reasoning"  # Main supervisor thinking
    TOOLS = "tools"  # Tool calling and parsing
    SUBAGENTS = "subagents"  # Specialized agent tasks
    PLANNING = "planning"  # TODO generation and planning
    EMBEDDINGS = "embeddings"  # Vector embeddings for RAG


# =============================================================================
# SQLAlchemy Models
# =============================================================================

class LLMProvider(Base):
    """
    Configured LLM provider (OpenAI, Anthropic, or custom OpenAI-compatible server).
    
    API keys are stored in LocalStack Secrets Manager, only the secret path is stored here.
    """
    __tablename__ = "llm_providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False, unique=True, index=True)
    provider_type = Column(
        Enum(ProviderType, name="provider_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    api_base_url = Column(Text, nullable=True)  # NULL for OpenAI/Anthropic, required for custom
    api_key_secret_path = Column(Text, nullable=True)  # Path in LocalStack Secrets Manager
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    validated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    models = relationship("LLMProviderModel", back_populates="provider", cascade="all, delete-orphan")
    global_configs = relationship("LLMGlobalConfig", back_populates="provider")
    user_configs = relationship("LLMUserConfig", back_populates="provider")

    def __repr__(self):
        return f"<LLMProvider(name={self.name}, type={self.provider_type}, enabled={self.enabled})>"


class LLMProviderModel(Base):
    """
    Model available from a provider with capabilities and cost information.
    """
    __tablename__ = "llm_provider_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("llm_providers.id", ondelete="CASCADE"), nullable=False, index=True)
    model_name = Column(String(255), nullable=False)
    supports_tools = Column(Boolean, default=True, nullable=False)
    supports_embeddings = Column(Boolean, default=False, nullable=False)
    context_window = Column(Integer, default=4096, nullable=False)
    cost_per_1k_input_tokens = Column(Numeric(10, 6), nullable=True)
    cost_per_1k_output_tokens = Column(Numeric(10, 6), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    provider = relationship("LLMProvider", back_populates="models")

    __table_args__ = (
        UniqueConstraint("provider_id", "model_name", name="uq_provider_model"),
    )

    def __repr__(self):
        return f"<LLMProviderModel(provider_id={self.provider_id}, model={self.model_name})>"


class LLMGlobalConfig(Base):
    """
    Global default model configuration for each interaction type.
    
    This is the system-wide default used when no user-specific override exists.
    """
    __tablename__ = "llm_global_config"

    interaction_type = Column(
        Enum(InteractionType, name="interaction_type_enum", values_callable=lambda x: [e.value for e in x]),
        primary_key=True
    )
    provider_id = Column(UUID(as_uuid=True), ForeignKey("llm_providers.id", ondelete="RESTRICT"), nullable=False)
    model_name = Column(String(255), nullable=False)
    temperature = Column(Numeric(3, 2), default=Decimal("0.7"), nullable=False)
    max_tokens = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    provider = relationship("LLMProvider", back_populates="global_configs")

    __table_args__ = (
        ForeignKeyConstraint(
            ["provider_id", "model_name"],
            ["llm_provider_models.provider_id", "llm_provider_models.model_name"],
            ondelete="RESTRICT"
        ),
    )

    def __repr__(self):
        return f"<LLMGlobalConfig(type={self.interaction_type}, model={self.model_name}, temp={self.temperature})>"


class LLMUserConfig(Base):
    """
    Per-user override of global model configuration.
    
    Allows individual users to customize their model preferences.
    """
    __tablename__ = "llm_user_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    interaction_type = Column(
        Enum(InteractionType, name="interaction_type_enum"),
        nullable=False,
        index=True
    )
    provider_id = Column(UUID(as_uuid=True), ForeignKey("llm_providers.id", ondelete="CASCADE"), nullable=False)
    model_name = Column(String(255), nullable=False)
    temperature = Column(Numeric(3, 2), default=Decimal("0.7"), nullable=False)
    max_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    provider = relationship("LLMProvider", back_populates="user_configs")

    __table_args__ = (
        UniqueConstraint("user_id", "interaction_type", name="uq_user_interaction"),
        ForeignKeyConstraint(
            ["provider_id", "model_name"],
            ["llm_provider_models.provider_id", "llm_provider_models.model_name"],
            ondelete="CASCADE"
        ),
    )

    def __repr__(self):
        return f"<LLMUserConfig(user={self.user_id}, type={self.interaction_type}, model={self.model_name})>"


# =============================================================================
# Pydantic Models for API
# =============================================================================

class ProviderCreate(BaseModel):
    """Request model for creating a new provider"""
    name: str = Field(..., min_length=1, max_length=255)
    provider_type: ProviderType
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None  # Will be encrypted and stored in LocalStack

    class Config:
        use_enum_values = True


class ProviderUpdate(BaseModel):
    """Request model for updating a provider"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    enabled: Optional[bool] = None

    class Config:
        use_enum_values = True


class ProviderResponse(BaseModel):
    """Response model for provider information"""
    id: str
    name: str
    provider_type: str
    api_base_url: Optional[str]
    enabled: bool
    validated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    models: List[str] = Field(default_factory=list, description="List of available model names")

    class Config:
        from_attributes = True
        use_enum_values = True


class ModelCreate(BaseModel):
    """Request model for adding a model to a provider"""
    model_name: str
    supports_tools: bool = True
    supports_embeddings: bool = False
    context_window: int = 4096
    cost_per_1k_input_tokens: Optional[float] = None
    cost_per_1k_output_tokens: Optional[float] = None


class ModelResponse(BaseModel):
    """Response model for model information"""
    id: str
    provider_id: str
    model_name: str
    supports_tools: bool
    supports_embeddings: bool
    context_window: int
    cost_per_1k_input_tokens: Optional[float]
    cost_per_1k_output_tokens: Optional[float]

    class Config:
        from_attributes = True


class InteractionConfigUpdate(BaseModel):
    """Request model for updating configuration for an interaction type.
    
    All fields are optional to support partial updates.
    When updating, only provided fields will be changed.
    """
    provider_id: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = None


class InteractionConfigResponse(BaseModel):
    """Response model for interaction configuration"""
    interaction_type: str
    provider_id: str
    model_name: str
    temperature: float
    max_tokens: Optional[int]
    updated_at: datetime

    class Config:
        from_attributes = True
        use_enum_values = True


class GlobalConfigResponse(BaseModel):
    """Response model for all interaction configurations"""
    reasoning: InteractionConfigResponse
    tools: InteractionConfigResponse
    subagents: InteractionConfigResponse
    planning: InteractionConfigResponse
    embeddings: InteractionConfigResponse

