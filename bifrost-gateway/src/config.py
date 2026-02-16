"""
Bifrost Gateway Configuration

Supports multiple adapters and AI backends with individual configuration.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.adapters.base import AdapterConfig
from src.backends.base import BackendConfig


class Settings(BaseSettings):
    """Bifrost Gateway settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # =========================================================================
    # SERVICE CONFIGURATION
    # =========================================================================
    APP_NAME: str = "Bifrost Gateway"
    APP_ENV: str = "development"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8050

    # Redis for conversation state (shared across adapters)
    REDIS_URL: str = "redis://redis:6379/3"

    # AWS / Secrets
    AWS_ENDPOINT_URL: str | None = "http://localstack:4566"
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None

    # =========================================================================
    # AI BACKEND SELECTION
    # =========================================================================
    # Which backend to use: norns, openai, anthropic, mcp
    AI_BACKEND: str = "norns"

    # =========================================================================
    # NORNS BACKEND
    # =========================================================================
    NORNS_API_URL: str = "http://hlidskjalf:8900"
    NORNS_LANGGRAPH_URL: str = "http://langgraph:2024"
    USE_LANGGRAPH: bool = True

    # =========================================================================
    # OPENAI BACKEND
    # =========================================================================
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 4096
    OPENAI_ORG_ID: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None  # For Azure OpenAI

    # =========================================================================
    # ANTHROPIC BACKEND
    # =========================================================================
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    ANTHROPIC_TEMPERATURE: float = 0.7
    ANTHROPIC_MAX_TOKENS: int = 4096

    # =========================================================================
    # MCP BACKEND
    # =========================================================================
    MCP_SERVER_URL: Optional[str] = None
    MCP_CHAT_TOOL: str = "chat"
    MCP_USE_SSE: bool = True

    # =========================================================================
    # GitLab Work Items / Norns queue
    # =========================================================================
    GITLAB_BASE_URL: str = "https://gitlab.ravenhelm.test"
    GITLAB_PROJECT_ID: int = 2
    GITLAB_PAT: str | None = None
    GITLAB_PAT_SECRET_NAME: str = "ravenhelm/dev/gitlab/mcp_service"
    GITLAB_WEBHOOK_SECRET: str | None = None
    GITLAB_WEBHOOK_SECRET_NAME: str = "ravenhelm/dev/gitlab/webhook/norns"
    WORKQUEUE_POLL_INTERVAL_SECONDS: int = 180

    # =========================================================================
    # CUSTOM SYSTEM PROMPT (used by direct backends)
    # =========================================================================
    SYSTEM_PROMPT: Optional[str] = None

    # =========================================================================
    # TELEGRAM ADAPTER
    # =========================================================================
    TELEGRAM_ENABLED: bool = True
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None
    TELEGRAM_ALLOWED_USERS: str = ""  # Comma-separated user IDs
    TELEGRAM_RATE_LIMIT_MESSAGES: int = 30
    TELEGRAM_RATE_LIMIT_WINDOW: int = 60

    # =========================================================================
    # SLACK ADAPTER (Future)
    # =========================================================================
    SLACK_ENABLED: bool = False
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_SIGNING_SECRET: Optional[str] = None
    SLACK_ALLOWED_USERS: str = ""
    SLACK_ALLOWED_CHANNELS: str = ""

    # =========================================================================
    # DISCORD ADAPTER (Future)
    # =========================================================================
    DISCORD_ENABLED: bool = False
    DISCORD_BOT_TOKEN: Optional[str] = None
    DISCORD_ALLOWED_USERS: str = ""
    DISCORD_ALLOWED_GUILDS: str = ""

    # =========================================================================
    # MATRIX ADAPTER (Future)
    # =========================================================================
    MATRIX_ENABLED: bool = False
    MATRIX_HOMESERVER: Optional[str] = None
    MATRIX_ACCESS_TOKEN: Optional[str] = None
    MATRIX_USER_ID: Optional[str] = None
    MATRIX_ALLOWED_ROOMS: str = ""

    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _parse_csv(self, value: str) -> set[str]:
        """Parse comma-separated string into set."""
        if not value:
            return set()
        return {item.strip() for item in value.split(",") if item.strip()}
    
    def get_telegram_config(self) -> AdapterConfig:
        """Get Telegram adapter configuration."""
        return AdapterConfig(
            name="telegram",
            enabled=self.TELEGRAM_ENABLED and bool(self.TELEGRAM_BOT_TOKEN),
            api_token=self.TELEGRAM_BOT_TOKEN,
            webhook_secret=self.TELEGRAM_WEBHOOK_SECRET,
            allowed_users=self._parse_csv(self.TELEGRAM_ALLOWED_USERS),
            rate_limit_messages=self.TELEGRAM_RATE_LIMIT_MESSAGES,
            rate_limit_window=self.TELEGRAM_RATE_LIMIT_WINDOW,
            extra={"redis_url": self.REDIS_URL},
        )
    
    def get_slack_config(self) -> AdapterConfig:
        """Get Slack adapter configuration."""
        return AdapterConfig(
            name="slack",
            enabled=self.SLACK_ENABLED and bool(self.SLACK_BOT_TOKEN),
            api_token=self.SLACK_BOT_TOKEN,
            webhook_secret=self.SLACK_SIGNING_SECRET,
            allowed_users=self._parse_csv(self.SLACK_ALLOWED_USERS),
            allowed_channels=self._parse_csv(self.SLACK_ALLOWED_CHANNELS),
            extra={"redis_url": self.REDIS_URL},
        )
    
    def get_discord_config(self) -> AdapterConfig:
        """Get Discord adapter configuration."""
        return AdapterConfig(
            name="discord",
            enabled=self.DISCORD_ENABLED and bool(self.DISCORD_BOT_TOKEN),
            api_token=self.DISCORD_BOT_TOKEN,
            allowed_users=self._parse_csv(self.DISCORD_ALLOWED_USERS),
            extra={
                "redis_url": self.REDIS_URL,
                "allowed_guilds": self._parse_csv(self.DISCORD_ALLOWED_GUILDS),
            },
        )
    
    def get_matrix_config(self) -> AdapterConfig:
        """Get Matrix adapter configuration."""
        return AdapterConfig(
            name="matrix",
            enabled=self.MATRIX_ENABLED and bool(self.MATRIX_ACCESS_TOKEN),
            api_token=self.MATRIX_ACCESS_TOKEN,
            allowed_channels=self._parse_csv(self.MATRIX_ALLOWED_ROOMS),
            extra={
                "redis_url": self.REDIS_URL,
                "homeserver": self.MATRIX_HOMESERVER,
                "user_id": self.MATRIX_USER_ID,
            },
        )
    
    def get_all_adapter_configs(self) -> dict[str, AdapterConfig]:
        """Get all adapter configurations."""
        return {
            "telegram": self.get_telegram_config(),
            "slack": self.get_slack_config(),
            "discord": self.get_discord_config(),
            "matrix": self.get_matrix_config(),
        }
    
    def get_enabled_adapter_configs(self) -> dict[str, AdapterConfig]:
        """Get only enabled adapter configurations."""
        all_configs = self.get_all_adapter_configs()
        return {
            name: config 
            for name, config in all_configs.items() 
            if config.enabled
        }
    
    # =========================================================================
    # BACKEND CONFIGURATION METHODS
    # =========================================================================
    
    def get_norns_backend_config(self) -> BackendConfig:
        """Get Norns backend configuration."""
        return BackendConfig(
            name="norns",
            enabled=self.AI_BACKEND == "norns",
            api_url=self.NORNS_LANGGRAPH_URL if self.USE_LANGGRAPH else self.NORNS_API_URL,
            extra={
                "use_langgraph": self.USE_LANGGRAPH,
                "direct_url": self.NORNS_API_URL,
            },
        )
    
    def get_openai_backend_config(self) -> BackendConfig:
        """Get OpenAI backend configuration."""
        return BackendConfig(
            name="openai",
            enabled=self.AI_BACKEND == "openai" and bool(self.OPENAI_API_KEY),
            api_key=self.OPENAI_API_KEY,
            model=self.OPENAI_MODEL,
            temperature=self.OPENAI_TEMPERATURE,
            max_tokens=self.OPENAI_MAX_TOKENS,
            system_prompt=self.SYSTEM_PROMPT,
            extra={
                "organization": self.OPENAI_ORG_ID,
                "base_url": self.OPENAI_BASE_URL,
            },
        )
    
    def get_anthropic_backend_config(self) -> BackendConfig:
        """Get Anthropic backend configuration."""
        return BackendConfig(
            name="anthropic",
            enabled=self.AI_BACKEND == "anthropic" and bool(self.ANTHROPIC_API_KEY),
            api_key=self.ANTHROPIC_API_KEY,
            model=self.ANTHROPIC_MODEL,
            temperature=self.ANTHROPIC_TEMPERATURE,
            max_tokens=self.ANTHROPIC_MAX_TOKENS,
            system_prompt=self.SYSTEM_PROMPT,
        )
    
    def get_mcp_backend_config(self) -> BackendConfig:
        """Get MCP backend configuration."""
        return BackendConfig(
            name="mcp",
            enabled=self.AI_BACKEND == "mcp" and bool(self.MCP_SERVER_URL),
            api_url=self.MCP_SERVER_URL,
            system_prompt=self.SYSTEM_PROMPT,
            extra={
                "chat_tool": self.MCP_CHAT_TOOL,
                "use_sse": self.MCP_USE_SSE,
            },
        )
    
    def get_active_backend_config(self) -> BackendConfig:
        """Get the configuration for the currently selected backend."""
        backend_configs = {
            "norns": self.get_norns_backend_config,
            "openai": self.get_openai_backend_config,
            "anthropic": self.get_anthropic_backend_config,
            "mcp": self.get_mcp_backend_config,
        }
        
        config_fn = backend_configs.get(self.AI_BACKEND)
        if config_fn:
            return config_fn()
        
        # Default to norns
        return self.get_norns_backend_config()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
