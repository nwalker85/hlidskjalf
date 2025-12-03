"""
Adapter Registry — Dynamic adapter loading and management.

This module handles the registration, discovery, and lifecycle
of messaging platform adapters.
"""

import structlog
from typing import Optional, Type

from src.adapters.base import BaseAdapter, AdapterConfig

logger = structlog.get_logger(__name__)

# Global registry of adapter classes
ADAPTER_REGISTRY: dict[str, Type[BaseAdapter]] = {}

# Active adapter instances
_active_adapters: dict[str, BaseAdapter] = {}


def register_adapter(name: str):
    """
    Decorator to register an adapter class.
    
    Example:
        @register_adapter("telegram")
        class TelegramAdapter(BaseAdapter):
            ...
    """
    def decorator(cls: Type[BaseAdapter]) -> Type[BaseAdapter]:
        if not issubclass(cls, BaseAdapter):
            raise TypeError(f"{cls.__name__} must inherit from BaseAdapter")
        
        ADAPTER_REGISTRY[name] = cls
        logger.debug("adapter_registered", name=name, cls=cls.__name__)
        return cls
    
    return decorator


def get_adapter_class(name: str) -> Optional[Type[BaseAdapter]]:
    """Get an adapter class by name."""
    return ADAPTER_REGISTRY.get(name)


def get_adapter(name: str) -> Optional[BaseAdapter]:
    """Get an active adapter instance by name."""
    return _active_adapters.get(name)


def get_enabled_adapters() -> dict[str, BaseAdapter]:
    """Get all enabled and initialized adapters."""
    return {
        name: adapter 
        for name, adapter in _active_adapters.items() 
        if adapter.is_enabled and adapter.is_initialized
    }


def list_registered_adapters() -> list[str]:
    """List all registered adapter names."""
    return list(ADAPTER_REGISTRY.keys())


async def create_adapter(name: str, config: AdapterConfig) -> Optional[BaseAdapter]:
    """
    Create and initialize an adapter instance.
    
    Args:
        name: The adapter name (must be registered)
        config: Configuration for the adapter
        
    Returns:
        The initialized adapter, or None if creation failed
    """
    adapter_cls = ADAPTER_REGISTRY.get(name)
    if adapter_cls is None:
        logger.error("adapter_not_found", name=name, available=list(ADAPTER_REGISTRY.keys()))
        return None
    
    try:
        adapter = adapter_cls(config)
        await adapter.initialize()
        _active_adapters[name] = adapter
        logger.info("adapter_created", name=name, enabled=adapter.is_enabled)
        return adapter
    except Exception as e:
        logger.error("adapter_creation_failed", name=name, error=str(e))
        return None


async def initialize_adapters(configs: dict[str, AdapterConfig]) -> dict[str, BaseAdapter]:
    """
    Initialize all configured adapters.
    
    Args:
        configs: Map of adapter name to configuration
        
    Returns:
        Map of adapter name to initialized adapter instance
    """
    results = {}
    
    for name, config in configs.items():
        if not config.enabled:
            logger.debug("adapter_disabled", name=name)
            continue
        
        adapter = await create_adapter(name, config)
        if adapter:
            results[name] = adapter
    
    logger.info(
        "adapters_initialized",
        total=len(results),
        names=list(results.keys()),
    )
    return results


async def shutdown_adapters() -> None:
    """Shutdown all active adapters."""
    for name, adapter in list(_active_adapters.items()):
        try:
            await adapter.shutdown()
            logger.info("adapter_shutdown", name=name)
        except Exception as e:
            logger.error("adapter_shutdown_failed", name=name, error=str(e))
        finally:
            del _active_adapters[name]


def set_message_handler_for_all(handler) -> None:
    """Set the message handler for all active adapters."""
    for adapter in _active_adapters.values():
        adapter.set_message_handler(handler)


# =============================================================================
# Auto-import adapters to register them
# =============================================================================

def _auto_register_adapters():
    """Import all adapter modules to trigger registration."""
    # Import built-in adapters
    try:
        from src.adapters import telegram  # noqa: F401
        logger.debug("loaded_adapter_module", module="telegram")
    except ImportError as e:
        logger.warning("adapter_import_failed", module="telegram", error=str(e))
    
    try:
        from src.adapters import slack  # noqa: F401
        logger.debug("loaded_adapter_module", module="slack")
    except ImportError as e:
        logger.warning("adapter_import_failed", module="slack", error=str(e))
    
    # Future adapters will be imported here:
    # try:
    #     from src.adapters import discord  # noqa: F401
    # except ImportError:
    #     pass


# Auto-register on module import
_auto_register_adapters()

