"""Cost tracking module for AI/LLM usage and resource consumption.

Tracks costs per:
- Organization (tenant)
- Model provider (OpenAI, Anthropic, etc.)
- Model name (gpt-4, claude-3, etc.)
- Operation type (inference, embedding, etc.)

Supports:
- Real-time cost calculation based on token usage
- Budget alerts and limits
- Cost aggregation by time periods
- Integration with billing systems
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.core.cache import cache_get, cache_set, cache_increment

logger = get_logger(__name__)


class ModelProvider(str, Enum):
    """Supported AI model providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"
    COHERE = "cohere"
    CUSTOM = "custom"


class OperationType(str, Enum):
    """Types of AI operations."""

    INFERENCE = "inference"
    EMBEDDING = "embedding"
    FINE_TUNING = "fine_tuning"
    IMAGE_GENERATION = "image_generation"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"


@dataclass
class ModelPricing:
    """Pricing information for a model.

    Prices are per 1000 tokens (or per unit for other operations).
    """

    input_price_per_1k: Decimal  # Price per 1000 input tokens
    output_price_per_1k: Decimal  # Price per 1000 output tokens
    currency: str = "USD"

    def calculate_cost(
        self, input_tokens: int, output_tokens: int
    ) -> Decimal:
        """Calculate total cost for a request."""
        input_cost = (Decimal(input_tokens) / 1000) * self.input_price_per_1k
        output_cost = (Decimal(output_tokens) / 1000) * self.output_price_per_1k
        return input_cost + output_cost


# Default pricing table (should be kept updated)
# Prices as of late 2024 - update regularly
MODEL_PRICING: dict[str, ModelPricing] = {
    # OpenAI
    "gpt-4-turbo": ModelPricing(
        input_price_per_1k=Decimal("0.01"),
        output_price_per_1k=Decimal("0.03"),
    ),
    "gpt-4": ModelPricing(
        input_price_per_1k=Decimal("0.03"),
        output_price_per_1k=Decimal("0.06"),
    ),
    "gpt-4o": ModelPricing(
        input_price_per_1k=Decimal("0.005"),
        output_price_per_1k=Decimal("0.015"),
    ),
    "gpt-4o-mini": ModelPricing(
        input_price_per_1k=Decimal("0.00015"),
        output_price_per_1k=Decimal("0.0006"),
    ),
    "gpt-3.5-turbo": ModelPricing(
        input_price_per_1k=Decimal("0.0005"),
        output_price_per_1k=Decimal("0.0015"),
    ),
    # Anthropic
    "claude-3-opus": ModelPricing(
        input_price_per_1k=Decimal("0.015"),
        output_price_per_1k=Decimal("0.075"),
    ),
    "claude-3-sonnet": ModelPricing(
        input_price_per_1k=Decimal("0.003"),
        output_price_per_1k=Decimal("0.015"),
    ),
    "claude-3-haiku": ModelPricing(
        input_price_per_1k=Decimal("0.00025"),
        output_price_per_1k=Decimal("0.00125"),
    ),
    "claude-3.5-sonnet": ModelPricing(
        input_price_per_1k=Decimal("0.003"),
        output_price_per_1k=Decimal("0.015"),
    ),
    # Embeddings
    "text-embedding-3-small": ModelPricing(
        input_price_per_1k=Decimal("0.00002"),
        output_price_per_1k=Decimal("0"),
    ),
    "text-embedding-3-large": ModelPricing(
        input_price_per_1k=Decimal("0.00013"),
        output_price_per_1k=Decimal("0"),
    ),
}


class UsageRecord(BaseModel):
    """Record of a single AI usage event."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Organization context
    org_id: str
    user_id: str | None = None
    agent_id: str | None = None

    # Model information
    provider: ModelProvider
    model_name: str
    operation_type: OperationType = OperationType.INFERENCE

    # Token usage
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # Cost
    cost_usd: Decimal = Decimal("0")
    currency: str = "USD"

    # Request metadata
    request_id: str | None = None
    trace_id: str | None = None
    latency_ms: float | None = None

    # Additional context
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }


class CostTracker:
    """Tracks and aggregates AI usage costs.

    Provides real-time cost tracking with Redis-backed counters
    for fast aggregation.
    """

    # Cache key patterns
    DAILY_COST_KEY = "cost:{org_id}:daily:{date}"
    MONTHLY_COST_KEY = "cost:{org_id}:monthly:{year_month}"
    MODEL_COST_KEY = "cost:{org_id}:model:{model}:{year_month}"
    BUDGET_KEY = "budget:{org_id}:monthly"

    def __init__(self):
        self._pricing = MODEL_PRICING.copy()

    def register_pricing(self, model_name: str, pricing: ModelPricing) -> None:
        """Register custom pricing for a model."""
        self._pricing[model_name] = pricing

    def get_pricing(self, model_name: str) -> ModelPricing | None:
        """Get pricing for a model."""
        # Try exact match first
        if model_name in self._pricing:
            return self._pricing[model_name]

        # Try prefix match (e.g., "gpt-4-turbo-2024-01-01" -> "gpt-4-turbo")
        for key in self._pricing:
            if model_name.startswith(key):
                return self._pricing[key]

        return None

    def calculate_cost(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Decimal:
        """Calculate cost for a model usage."""
        pricing = self.get_pricing(model_name)
        if not pricing:
            logger.warning(
                "No pricing found for model",
                model=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            return Decimal("0")

        return pricing.calculate_cost(input_tokens, output_tokens)

    async def record_usage(
        self,
        org_id: str,
        provider: ModelProvider,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        *,
        operation_type: OperationType = OperationType.INFERENCE,
        user_id: str | None = None,
        agent_id: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        latency_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UsageRecord:
        """Record AI usage and update cost counters.

        Args:
            org_id: Organization ID
            provider: Model provider
            model_name: Name of the model used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            operation_type: Type of operation
            user_id: Optional user ID
            agent_id: Optional agent ID
            request_id: Optional request ID
            trace_id: Optional trace ID
            latency_ms: Optional latency in milliseconds
            metadata: Additional metadata

        Returns:
            UsageRecord with calculated cost
        """
        # Calculate cost
        cost = self.calculate_cost(model_name, input_tokens, output_tokens)

        # Create usage record
        record = UsageRecord(
            org_id=org_id,
            user_id=user_id,
            agent_id=agent_id,
            provider=provider,
            model_name=model_name,
            operation_type=operation_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=cost,
            request_id=request_id,
            trace_id=trace_id,
            latency_ms=latency_ms,
            metadata=metadata or {},
        )

        # Update cost counters in Redis
        await self._update_counters(record)

        # Log for observability
        logger.info(
            "AI usage recorded",
            org_id=org_id,
            provider=provider.value,
            model=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=str(cost),
            agent_id=agent_id,
        )

        # Check budget alerts
        await self._check_budget_alerts(org_id, cost)

        return record

    async def _update_counters(self, record: UsageRecord) -> None:
        """Update Redis cost counters."""
        now = record.timestamp
        date_str = now.strftime("%Y-%m-%d")
        year_month = now.strftime("%Y-%m")

        # Convert cost to cents for integer operations
        cost_cents = int(record.cost_usd * 100)

        try:
            # Update daily counter
            daily_key = self.DAILY_COST_KEY.format(
                org_id=record.org_id, date=date_str
            )
            await cache_increment(daily_key, cost_cents)

            # Update monthly counter
            monthly_key = self.MONTHLY_COST_KEY.format(
                org_id=record.org_id, year_month=year_month
            )
            await cache_increment(monthly_key, cost_cents)

            # Update model-specific counter
            model_key = self.MODEL_COST_KEY.format(
                org_id=record.org_id,
                model=record.model_name.replace(".", "_"),
                year_month=year_month,
            )
            await cache_increment(model_key, cost_cents)

        except Exception as e:
            logger.warning("Failed to update cost counters", error=str(e))

    async def _check_budget_alerts(self, org_id: str, cost: Decimal) -> None:
        """Check if usage is approaching or exceeding budget."""
        try:
            budget_key = self.BUDGET_KEY.format(org_id=org_id)
            budget_data = await cache_get(budget_key)

            if not budget_data:
                return

            monthly_budget = Decimal(str(budget_data.get("monthly_limit", 0)))
            alert_threshold = Decimal(str(budget_data.get("alert_threshold", 0.8)))

            if monthly_budget <= 0:
                return

            # Get current monthly spend
            now = datetime.now(timezone.utc)
            monthly_key = self.MONTHLY_COST_KEY.format(
                org_id=org_id, year_month=now.strftime("%Y-%m")
            )
            current_spend_cents = await cache_get(monthly_key) or 0
            current_spend = Decimal(current_spend_cents) / 100

            usage_ratio = current_spend / monthly_budget

            if usage_ratio >= 1:
                logger.warning(
                    "Budget exceeded",
                    org_id=org_id,
                    current_spend=str(current_spend),
                    monthly_budget=str(monthly_budget),
                )
            elif usage_ratio >= alert_threshold:
                logger.warning(
                    "Budget alert threshold reached",
                    org_id=org_id,
                    current_spend=str(current_spend),
                    monthly_budget=str(monthly_budget),
                    usage_percent=f"{usage_ratio * 100:.1f}%",
                )

        except Exception as e:
            logger.warning("Failed to check budget alerts", error=str(e))

    async def get_daily_cost(self, org_id: str, date: str | None = None) -> Decimal:
        """Get total cost for a specific day."""
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        key = self.DAILY_COST_KEY.format(org_id=org_id, date=date)
        cost_cents = await cache_get(key) or 0
        return Decimal(cost_cents) / 100

    async def get_monthly_cost(
        self, org_id: str, year_month: str | None = None
    ) -> Decimal:
        """Get total cost for a specific month."""
        if year_month is None:
            year_month = datetime.now(timezone.utc).strftime("%Y-%m")

        key = self.MONTHLY_COST_KEY.format(org_id=org_id, year_month=year_month)
        cost_cents = await cache_get(key) or 0
        return Decimal(cost_cents) / 100

    async def set_monthly_budget(
        self,
        org_id: str,
        monthly_limit: Decimal,
        alert_threshold: Decimal = Decimal("0.8"),
    ) -> None:
        """Set monthly budget for an organization."""
        key = self.BUDGET_KEY.format(org_id=org_id)
        await cache_set(
            key,
            {
                "monthly_limit": str(monthly_limit),
                "alert_threshold": str(alert_threshold),
            },
        )
        logger.info(
            "Monthly budget set",
            org_id=org_id,
            monthly_limit=str(monthly_limit),
            alert_threshold=str(alert_threshold),
        )


# Global cost tracker instance
cost_tracker = CostTracker()


# Convenience functions
async def track_llm_usage(
    org_id: str,
    provider: str,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    **kwargs: Any,
) -> UsageRecord:
    """Track LLM usage using the global cost tracker."""
    return await cost_tracker.record_usage(
        org_id=org_id,
        provider=ModelProvider(provider),
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        **kwargs,
    )


async def get_org_monthly_cost(org_id: str) -> Decimal:
    """Get current month's cost for an organization."""
    return await cost_tracker.get_monthly_cost(org_id)
