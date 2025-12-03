"""
Bifrost Adapters — Messaging Platform Integrations

This module provides the extensible adapter system for integrating
external messaging platforms with the Norns.

To add a new adapter:
1. Create a new file in this directory (e.g., slack.py)
2. Implement the BaseAdapter interface
3. Register it in ADAPTER_REGISTRY
4. Add configuration in config.py

See docs/runbooks/RUNBOOK-020-add-bifrost-adapter.md for details.
"""

from src.adapters.base import (
    BaseAdapter,
    AdapterMessage,
    AdapterResponse,
    AdapterConfig,
    AdapterCapabilities,
)
from src.adapters.registry import (
    ADAPTER_REGISTRY,
    register_adapter,
    get_adapter,
    get_enabled_adapters,
    initialize_adapters,
    shutdown_adapters,
)

__all__ = [
    # Base classes
    "BaseAdapter",
    "AdapterMessage",
    "AdapterResponse",
    "AdapterConfig",
    "AdapterCapabilities",
    # Registry
    "ADAPTER_REGISTRY",
    "register_adapter",
    "get_adapter",
    "get_enabled_adapters",
    "initialize_adapters",
    "shutdown_adapters",
]

