"""
Bifrost AI Backends — Pluggable AI System Integrations

This module provides the extensible backend system for connecting
different AI systems to Bifrost.

To add a new AI backend:
1. Create a new file in this directory (e.g., claude.py)
2. Implement the BaseBackend interface
3. Register it in BACKEND_REGISTRY
4. Add configuration in config.py

See docs/runbooks/RUNBOOK-021-add-bifrost-ai-backend.md for details.
"""

from src.backends.base import (
    BaseBackend,
    BackendConfig,
    BackendCapabilities,
    ChatRequest,
    ChatResponse,
)
from src.backends.registry import (
    BACKEND_REGISTRY,
    register_backend,
    get_backend,
    get_active_backend,
    initialize_backend,
    shutdown_backend,
)

__all__ = [
    # Base classes
    "BaseBackend",
    "BackendConfig",
    "BackendCapabilities",
    "ChatRequest",
    "ChatResponse",
    # Registry
    "BACKEND_REGISTRY",
    "register_backend",
    "get_backend",
    "get_active_backend",
    "initialize_backend",
    "shutdown_backend",
]

