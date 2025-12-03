"""
Port Registry Service
Manages port allocations with automatic assignment and conflict prevention
"""

import asyncio
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.core.config import get_settings
from src.models.registry import (
    PortAllocation,
    PortType,
    Environment,
    PortRequest,
    PortAllocationResponse,
)

logger = get_logger(__name__)
settings = get_settings()


class PortRegistryService:
    """
    Port Registry Service
    
    Handles automatic port assignment with the following strategy:
    - HTTP ports: 8000-8399
    - HTTPS ports: 8400-8599
    - gRPC ports: 9000-9199
    - Metrics ports: 9200-9299
    
    Each project gets a "slot" of 10 ports per type to ensure consistent allocation.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._lock = asyncio.Lock()
    
    async def allocate_port(self, request: PortRequest) -> PortAllocationResponse:
        """
        Allocate a port for a service.
        
        If preferred_port is specified, validates and uses it.
        Otherwise, auto-assigns the next available port in the range.
        """
        async with self._lock:  # Ensure atomic port assignment
            # Check if this exact allocation already exists
            existing = await self._get_existing_allocation(
                request.project_id,
                request.service_name,
                request.port_type,
                request.environment
            )
            
            if existing:
                logger.info(
                    "Port already allocated",
                    project_id=request.project_id,
                    service=request.service_name,
                    port=existing.port
                )
                return PortAllocationResponse.model_validate(existing)
            
            # Determine port
            if request.preferred_port:
                port = await self._validate_preferred_port(
                    request.preferred_port,
                    request.environment
                )
                auto_assigned = False
            else:
                port = await self._find_next_available_port(
                    request.port_type,
                    request.environment
                )
                auto_assigned = True
            
            # Create allocation
            allocation = PortAllocation(
                project_id=request.project_id,
                port=port,
                port_type=request.port_type,
                environment=request.environment,
                service_name=request.service_name,
                internal_port=request.internal_port,
                description=request.description,
                auto_assigned=auto_assigned,
            )
            
            self.session.add(allocation)
            await self.session.commit()
            await self.session.refresh(allocation)
            
            logger.info(
                "Port allocated",
                project_id=request.project_id,
                service=request.service_name,
                port=port,
                auto_assigned=auto_assigned
            )
            
            return PortAllocationResponse.model_validate(allocation)
    
    async def _get_existing_allocation(
        self,
        project_id: str,
        service_name: str,
        port_type: PortType,
        environment: Environment
    ) -> Optional[PortAllocation]:
        """Check if allocation already exists"""
        result = await self.session.execute(
            select(PortAllocation).where(
                and_(
                    PortAllocation.project_id == project_id,
                    PortAllocation.service_name == service_name,
                    PortAllocation.port_type == port_type,
                    PortAllocation.environment == environment,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _validate_preferred_port(
        self,
        port: int,
        environment: Environment
    ) -> int:
        """Validate that preferred port is available"""
        # Check reserved ports
        if port in settings.RESERVED_PORTS:
            raise ValueError(f"Port {port} is reserved for system services")
        
        # Check if already allocated
        result = await self.session.execute(
            select(PortAllocation).where(
                and_(
                    PortAllocation.port == port,
                    PortAllocation.environment == environment,
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise ValueError(
                f"Port {port} is already allocated to {existing.project_id}/{existing.service_name}"
            )
        
        return port
    
    async def _find_next_available_port(
        self,
        port_type: PortType,
        environment: Environment
    ) -> int:
        """Find the next available port in the appropriate range"""
        # Get port range based on type
        start, end = self._get_port_range(port_type)
        
        # Get all allocated ports in this range and environment
        result = await self.session.execute(
            select(PortAllocation.port).where(
                and_(
                    PortAllocation.port >= start,
                    PortAllocation.port <= end,
                    PortAllocation.environment == environment,
                )
            ).order_by(PortAllocation.port)
        )
        allocated_ports = set(row[0] for row in result.fetchall())
        
        # Also exclude reserved ports
        reserved = set(settings.RESERVED_PORTS)
        unavailable = allocated_ports | reserved
        
        # Find first available port
        for port in range(start, end + 1):
            if port not in unavailable:
                return port
        
        raise ValueError(
            f"No available ports in range {start}-{end} for {port_type.value}"
        )
    
    def _get_port_range(self, port_type: PortType) -> tuple[int, int]:
        """Get port range for a given type"""
        ranges = {
            PortType.HTTP: (settings.PORT_RANGE_HTTP_START, settings.PORT_RANGE_HTTPS_START - 1),
            PortType.HTTPS: (settings.PORT_RANGE_HTTPS_START, settings.PORT_RANGE_HTTPS_END),
            PortType.GRPC: (settings.PORT_RANGE_GRPC_START, settings.PORT_RANGE_GRPC_END),
            PortType.METRICS: (settings.PORT_RANGE_METRICS_START, settings.PORT_RANGE_METRICS_END),
            PortType.DATABASE: (5400, 5499),
            PortType.CUSTOM: (7000, 7999),
        }
        return ranges.get(port_type, (8000, 8999))
    
    async def get_project_ports(
        self,
        project_id: str,
        environment: Optional[Environment] = None
    ) -> list[PortAllocationResponse]:
        """Get all port allocations for a project"""
        query = select(PortAllocation).where(
            PortAllocation.project_id == project_id
        )
        
        if environment:
            query = query.where(PortAllocation.environment == environment)
        
        result = await self.session.execute(query)
        allocations = result.scalars().all()
        
        return [PortAllocationResponse.model_validate(a) for a in allocations]
    
    async def release_port(self, allocation_id: int) -> bool:
        """Release a port allocation"""
        result = await self.session.execute(
            select(PortAllocation).where(PortAllocation.id == allocation_id)
        )
        allocation = result.scalar_one_or_none()
        
        if allocation:
            await self.session.delete(allocation)
            await self.session.commit()
            logger.info(
                "Port released",
                port=allocation.port,
                project_id=allocation.project_id
            )
            return True
        
        return False
    
    async def get_port_summary(self) -> dict:
        """Get summary of port allocations"""
        result = await self.session.execute(select(PortAllocation))
        allocations = result.scalars().all()
        
        # Calculate available ports per type
        port_ranges = {
            PortType.HTTP: self._get_port_range(PortType.HTTP),
            PortType.HTTPS: self._get_port_range(PortType.HTTPS),
            PortType.GRPC: self._get_port_range(PortType.GRPC),
            PortType.METRICS: self._get_port_range(PortType.METRICS),
        }
        
        summary = {
            "total_allocated": len(allocations),
            "by_type": {},
            "by_environment": {},
            "by_project": {},
        }
        
        for port_type, (start, end) in port_ranges.items():
            total_in_range = end - start + 1
            allocated_in_range = sum(
                1 for a in allocations 
                if a.port_type == port_type
            )
            summary["by_type"][port_type.value] = {
                "allocated": allocated_in_range,
                "available": total_in_range - allocated_in_range,
                "range": f"{start}-{end}"
            }
        
        for env in Environment:
            summary["by_environment"][env.value] = sum(
                1 for a in allocations if a.environment == env
            )
        
        for allocation in allocations:
            if allocation.project_id not in summary["by_project"]:
                summary["by_project"][allocation.project_id] = []
            summary["by_project"][allocation.project_id].append({
                "service": allocation.service_name,
                "port": allocation.port,
                "type": allocation.port_type.value,
                "environment": allocation.environment.value
            })
        
        return summary


async def allocate_project_ports(
    session: AsyncSession,
    project_id: str,
    services: list[dict],
    environment: Environment = Environment.MIDGARD
) -> list[PortAllocationResponse]:
    """
    Bulk allocate ports for a new project.
    
    Example services:
    [
        {"name": "api", "type": "https", "internal_port": 8000},
        {"name": "frontend", "type": "https", "internal_port": 3000},
        {"name": "worker", "type": "http", "internal_port": 8080},
        {"name": "metrics", "type": "metrics", "internal_port": 9090},
    ]
    """
    registry = PortRegistryService(session)
    allocations = []
    
    for service in services:
        request = PortRequest(
            project_id=project_id,
            service_name=service["name"],
            port_type=PortType(service.get("type", "http")),
            environment=environment,
            internal_port=service.get("internal_port"),
            description=service.get("description"),
        )
        allocation = await registry.allocate_port(request)
        allocations.append(allocation)
    
    return allocations

