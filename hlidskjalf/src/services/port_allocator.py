"""
Port Allocator Service
Manages port assignments across the platform, preventing conflicts
and updating the port registry.

Port Ranges:
- Platform: 8000-8099 (API), 3000-3099 (UI)
- Personal: 8100-8199 (API), 3100-3199 (UI)
- Work: 8200-8299 (API), 3200-3299 (UI)
- Sandbox: 8300-8399 (API), 3300-3399 (UI)
"""

import yaml
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.registry import (
    PortAllocation,
    PortType,
    ProjectCategory,
    Realm,
)

logger = structlog.get_logger(__name__)


@dataclass
class PortRange:
    """Defines a port range for allocation"""
    api_start: int
    api_end: int
    ui_start: int
    ui_end: int


# Port ranges by category
PORT_RANGES: dict[ProjectCategory, PortRange] = {
    ProjectCategory.PLATFORM: PortRange(8000, 8099, 3000, 3099),
    ProjectCategory.PERSONAL: PortRange(8100, 8199, 3100, 3199),
    ProjectCategory.WORK: PortRange(8200, 8299, 3200, 3299),
    ProjectCategory.SANDBOX: PortRange(8300, 8399, 3300, 3399),
}

# Category key mappings for port_registry.yaml
CATEGORY_KEYS = {
    ProjectCategory.PLATFORM: ("platform_api", "platform_ui"),
    ProjectCategory.PERSONAL: ("personal_api", "personal_ui"),
    ProjectCategory.WORK: ("work_api", "work_ui"),
    ProjectCategory.SANDBOX: ("sandbox_api", "sandbox_ui"),
}


class PortAllocator:
    """
    Manages port allocation across the platform.
    
    Reads from and updates config/port_registry.yaml to track
    next available ports and prevent conflicts.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        registry_path: Optional[Path] = None
    ):
        self.db = db
        self.registry_path = registry_path or Path("config/port_registry.yaml")
        self._registry_cache: Optional[dict] = None
    
    def _load_registry(self) -> dict:
        """Load the port registry YAML file"""
        if self._registry_cache is not None:
            return self._registry_cache
        
        if not self.registry_path.exists():
            logger.warning("Port registry not found", path=str(self.registry_path))
            return {
                "version": "1.0.0",
                "ranges": {},
                "ports": [],
                "next_available": {
                    "platform_api": 8000,
                    "platform_ui": 3000,
                    "personal_api": 8100,
                    "personal_ui": 3100,
                    "work_api": 8200,
                    "work_ui": 3200,
                    "sandbox_api": 8300,
                    "sandbox_ui": 3300,
                }
            }
        
        with open(self.registry_path) as f:
            self._registry_cache = yaml.safe_load(f)
        
        return self._registry_cache
    
    def _save_registry(self, registry: dict) -> None:
        """Save updates to the port registry YAML file"""
        with open(self.registry_path, 'w') as f:
            yaml.dump(registry, f, default_flow_style=False, sort_keys=False)
        
        self._registry_cache = registry
        logger.info("Port registry updated", path=str(self.registry_path))
    
    def get_next_available(
        self,
        category: ProjectCategory
    ) -> Tuple[int, int]:
        """
        Get the next available API and UI ports for a category.
        
        Returns:
            Tuple of (api_port, ui_port)
        """
        registry = self._load_registry()
        api_key, ui_key = CATEGORY_KEYS[category]
        
        next_available = registry.get("next_available", {})
        port_range = PORT_RANGES[category]
        
        api_port = next_available.get(api_key, port_range.api_start)
        ui_port = next_available.get(ui_key, port_range.ui_start)
        
        return api_port, ui_port
    
    async def is_port_available(
        self,
        port: int,
        environment: Realm = Realm.MIDGARD
    ) -> bool:
        """Check if a port is available in the given environment"""
        result = await self.db.execute(
            select(PortAllocation).where(
                PortAllocation.port == port,
                PortAllocation.environment == environment
            )
        )
        return result.scalar_one_or_none() is None
    
    async def allocate_ports(
        self,
        project_id: str,
        category: ProjectCategory,
        services: list[str] = None,
        environment: Realm = Realm.MIDGARD
    ) -> dict[str, int]:
        """
        Allocate ports for a project based on its category.
        
        Args:
            project_id: The project identifier
            category: Project category (determines port range)
            services: List of service names (defaults to ["api", "ui"])
            environment: Target environment
            
        Returns:
            Dictionary mapping service names to allocated ports
        """
        if services is None:
            services = ["api", "ui"]
        
        registry = self._load_registry()
        api_key, ui_key = CATEGORY_KEYS[category]
        port_range = PORT_RANGES[category]
        next_available = registry.get("next_available", {})
        
        allocations = {}
        
        for service in services:
            # Determine port type and range
            if service in ("api", "backend", "worker"):
                current_port = next_available.get(api_key, port_range.api_start)
                max_port = port_range.api_end
                port_type = PortType.HTTP
                key_to_update = api_key
            elif service in ("ui", "frontend", "web"):
                current_port = next_available.get(ui_key, port_range.ui_start)
                max_port = port_range.ui_end
                port_type = PortType.HTTP
                key_to_update = ui_key
            else:
                # Custom service - use API range
                current_port = next_available.get(api_key, port_range.api_start)
                max_port = port_range.api_end
                port_type = PortType.CUSTOM
                key_to_update = api_key
            
            # Find next available port
            allocated_port = None
            while current_port <= max_port:
                if await self.is_port_available(current_port, environment):
                    allocated_port = current_port
                    break
                current_port += 1
            
            if allocated_port is None:
                raise ValueError(
                    f"No available ports in range {port_range.api_start}-{max_port} "
                    f"for category {category.value}"
                )
            
            # Create database allocation
            allocation = PortAllocation(
                project_id=project_id,
                port=allocated_port,
                port_type=port_type,
                environment=environment,
                service_name=service,
                auto_assigned=True,
                description=f"Auto-allocated for {project_id}/{service}"
            )
            self.db.add(allocation)
            
            allocations[service] = allocated_port
            
            # Update next_available
            next_available[key_to_update] = allocated_port + 1
            
            logger.info(
                "Port allocated",
                project_id=project_id,
                service=service,
                port=allocated_port,
                category=category.value
            )
        
        # Save registry updates
        registry["next_available"] = next_available
        self._save_registry(registry)
        
        await self.db.commit()
        
        return allocations
    
    async def allocate_specific_port(
        self,
        project_id: str,
        service_name: str,
        port: int,
        port_type: PortType = PortType.HTTP,
        environment: Realm = Realm.MIDGARD,
        internal_port: Optional[int] = None,
        description: Optional[str] = None
    ) -> PortAllocation:
        """
        Allocate a specific port for a service.
        
        Raises:
            ValueError: If port is already allocated
        """
        if not await self.is_port_available(port, environment):
            raise ValueError(f"Port {port} is already allocated in {environment.value}")
        
        allocation = PortAllocation(
            project_id=project_id,
            port=port,
            port_type=port_type,
            environment=environment,
            service_name=service_name,
            internal_port=internal_port,
            auto_assigned=False,
            description=description or f"Manual allocation for {project_id}/{service_name}"
        )
        self.db.add(allocation)
        await self.db.commit()
        
        logger.info(
            "Specific port allocated",
            project_id=project_id,
            service=service_name,
            port=port
        )
        
        return allocation
    
    async def release_ports(
        self,
        project_id: str,
        environment: Optional[Realm] = None
    ) -> int:
        """
        Release all port allocations for a project.
        
        Args:
            project_id: The project identifier
            environment: Optional environment filter
            
        Returns:
            Number of ports released
        """
        query = select(PortAllocation).where(
            PortAllocation.project_id == project_id
        )
        
        if environment:
            query = query.where(PortAllocation.environment == environment)
        
        result = await self.db.execute(query)
        allocations = result.scalars().all()
        
        count = 0
        for allocation in allocations:
            await self.db.delete(allocation)
            count += 1
            logger.info(
                "Port released",
                project_id=project_id,
                service=allocation.service_name,
                port=allocation.port
            )
        
        await self.db.commit()
        return count
    
    def add_project_to_registry(
        self,
        project_id: str,
        category: ProjectCategory,
        api_port: int,
        ui_port: int,
        domain: str,
        realm: Realm,
        description: str,
        path: Optional[str] = None,
        git_remote: str = "gitlab.ravenhelm.test"
    ) -> None:
        """
        Add a project entry to the port registry YAML file.
        
        This adds the project under the appropriate category section
        (platform, personal, work, sandbox).
        """
        registry = self._load_registry()
        
        # Determine section key
        section_key = category.value
        if section_key not in registry:
            registry[section_key] = {}
        
        # Build project entry
        project_entry = {
            "api_port": api_port,
            "ui_port": ui_port,
            "domain": domain,
            "realm": realm.value,
            "status": "active",
            "git_remote": git_remote,
            "description": description
        }
        
        if path:
            project_entry["path"] = path
        
        registry[section_key][project_id] = project_entry
        
        self._save_registry(registry)
        
        logger.info(
            "Project added to registry",
            project_id=project_id,
            category=category.value,
            api_port=api_port,
            ui_port=ui_port
        )

