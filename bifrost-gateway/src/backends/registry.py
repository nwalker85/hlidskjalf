"""
Backend Registry — Dynamic AI backend loading and management.

This module handles the registration, discovery, and lifecycle
of AI backend integrations.
"""

import structlog
from typing import Optional, Type

from src.backends.base import BaseBackend, BackendConfig

logger = structlog.get_logger(__name__)

# Global registry of backend classes
BACKEND_REGISTRY: dict[str, Type[BaseBackend]] = {}

# Active backend instance (only one at a time)
_active_backend: Optional[BaseBackend] = None


def register_backend(name: str):
    """
    Decorator to register a backend class.
    
    Example:
        @register_backend("norns")
        class NornsBackend(BaseBackend):
            ...
    """
    def decorator(cls: Type[BaseBackend]) -> Type[BaseBackend]:
        if not issubclass(cls, BaseBackend):
            raise TypeError(f"{cls.__name__} must inherit from BaseBackend")
        
        BACKEND_REGISTRY[name] = cls
        logger.debug("backend_registered", name=name, cls=cls.__name__)
        return cls
    
    return decorator


def get_backend_class(name: str) -> Optional[Type[BaseBackend]]:
    """Get a backend class by name."""
    return BACKEND_REGISTRY.get(name)


def get_backend(name: str) -> Optional[BaseBackend]:
    """Get the active backend if it matches the name."""
    if _active_backend and _active_backend.name == name:
        return _active_backend
    return None


def get_active_backend() -> Optional[BaseBackend]:
    """Get the currently active backend."""
    return _active_backend


def list_registered_backends() -> list[str]:
    """List all registered backend names."""
    return list(BACKEND_REGISTRY.keys())


async def initialize_backend(name: str, config: BackendConfig) -> Optional[BaseBackend]:
    """
    Initialize and activate a backend.
    
    Only one backend can be active at a time. Initializing a new backend
    will shutdown the previous one.
    
    Args:
        name: The backend name (must be registered)
        config: Configuration for the backend
        
    Returns:
        The initialized backend, or None if initialization failed
    """
    global _active_backend
    
    # Shutdown existing backend
    if _active_backend:
        await shutdown_backend()
    
    # Get backend class
    backend_cls = BACKEND_REGISTRY.get(name)
    if backend_cls is None:
        logger.error("backend_not_found", name=name, available=list(BACKEND_REGISTRY.keys()))
        return None
    
    try:
        backend = backend_cls(config)
        await backend.initialize()
        _active_backend = backend
        logger.info("backend_initialized", name=name, enabled=backend.is_enabled)
        return backend
    except Exception as e:
        logger.error("backend_initialization_failed", name=name, error=str(e))
        return None


async def shutdown_backend() -> None:
    """Shutdown the active backend."""
    global _active_backend
    
    if _active_backend:
        try:
            await _active_backend.shutdown()
            logger.info("backend_shutdown", name=_active_backend.name)
        except Exception as e:
            logger.error("backend_shutdown_failed", name=_active_backend.name, error=str(e))
        finally:
            _active_backend = None


# =============================================================================
# Auto-import backends to register them
# =============================================================================

def _auto_register_backends():
    """Import all backend modules to trigger registration."""
    # Import built-in backends
    try:
        from src.backends import norns  # noqa: F401
        logger.debug("loaded_backend_module", module="norns")
    except ImportError as e:
        logger.warning("backend_import_failed", module="norns", error=str(e))
    
    try:
        from src.backends import openai_backend  # noqa: F401
        logger.debug("loaded_backend_module", module="openai")
    except ImportError as e:
        logger.warning("backend_import_failed", module="openai", error=str(e))
    
    try:
        from src.backends import anthropic_backend  # noqa: F401
        logger.debug("loaded_backend_module", module="anthropic")
    except ImportError as e:
        logger.warning("backend_import_failed", module="anthropic", error=str(e))
    
    try:
        from src.backends import mcp_backend  # noqa: F401
        logger.debug("loaded_backend_module", module="mcp")
    except ImportError as e:
        logger.warning("backend_import_failed", module="mcp", error=str(e))


# Auto-register on module import
_auto_register_backends()

