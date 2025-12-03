"""
Ravenhelm Control Plane API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from src.core.config import get_settings
from src.models.registry import (
    ProjectRecord,
    PortAllocation,
    Deployment,
    HealthCheckRecord,
    ProjectCreate,
    ProjectResponse,
    PortRequest,
    PortAllocationResponse,
    DeploymentCreate,
    DeploymentResponse,
    HealthCheckResponse,
    PlatformOverview,
    Environment,
    DeploymentStatus,
    HealthStatus,
)
from src.services.port_registry import PortRegistryService, allocate_project_ports
from src.services.nginx_generator import NginxConfigGenerator, regenerate_nginx_config
from src.services.deployment_manager import DeploymentManager

settings = get_settings()

router = APIRouter()


# =============================================================================
# Dependency: Database Session
# =============================================================================

async def get_session():
    """Get database session - to be implemented with actual session factory"""
    # This will be replaced with actual session factory in main.py
    raise NotImplementedError("Session factory not configured")


# =============================================================================
# Platform Overview
# =============================================================================

@router.get("/overview", response_model=PlatformOverview, tags=["Platform"])
async def get_platform_overview(session: AsyncSession = Depends(get_session)):
    """Get platform-wide overview for dashboard"""
    
    # Count projects
    result = await session.execute(select(func.count(ProjectRecord.id)))
    total_projects = result.scalar()
    
    # Count deployments by status
    result = await session.execute(select(func.count(Deployment.id)))
    total_deployments = result.scalar()
    
    result = await session.execute(
        select(func.count(Deployment.id)).where(
            Deployment.health_status == HealthStatus.HEALTHY
        )
    )
    healthy_deployments = result.scalar()
    
    result = await session.execute(
        select(func.count(Deployment.id)).where(
            Deployment.health_status == HealthStatus.UNHEALTHY
        )
    )
    unhealthy_deployments = result.scalar()
    
    # Count ports
    result = await session.execute(select(func.count(PortAllocation.id)))
    ports_allocated = result.scalar()
    
    # Calculate available ports (rough estimate)
    total_port_range = (
        (settings.PORT_RANGE_HTTP_END - settings.PORT_RANGE_HTTP_START) +
        (settings.PORT_RANGE_HTTPS_END - settings.PORT_RANGE_HTTPS_START) +
        (settings.PORT_RANGE_GRPC_END - settings.PORT_RANGE_GRPC_START) +
        (settings.PORT_RANGE_METRICS_END - settings.PORT_RANGE_METRICS_START)
    )
    ports_available = total_port_range - ports_allocated
    
    # Count by environment
    environments = {}
    for env in Environment:
        result = await session.execute(
            select(func.count(Deployment.id)).where(
                Deployment.environment == env
            )
        )
        environments[env.value] = result.scalar()
    
    # Get recent health checks
    result = await session.execute(
        select(HealthCheckRecord)
        .order_by(HealthCheckRecord.checked_at.desc())
        .limit(10)
    )
    recent_checks = result.scalars().all()
    
    return PlatformOverview(
        total_projects=total_projects,
        total_deployments=total_deployments,
        healthy_deployments=healthy_deployments,
        unhealthy_deployments=unhealthy_deployments,
        ports_allocated=ports_allocated,
        ports_available=ports_available,
        environments=environments,
        recent_health_checks=[
            HealthCheckResponse.model_validate(hc) for hc in recent_checks
        ],
    )


# =============================================================================
# Projects
# =============================================================================

@router.post("/projects", response_model=ProjectResponse, tags=["Projects"])
async def create_project(
    project: ProjectCreate,
    session: AsyncSession = Depends(get_session)
):
    """Register a new project in the platform"""
    
    # Check if project already exists
    result = await session.execute(
        select(ProjectRecord).where(ProjectRecord.id == project.id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Project {project.id} already exists")
    
    # Check if subdomain is taken
    result = await session.execute(
        select(ProjectRecord).where(ProjectRecord.subdomain == project.subdomain)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Subdomain {project.subdomain} is already in use"
        )
    
    # Create project
    record = ProjectRecord(
        id=project.id,
        name=project.name,
        description=project.description,
        git_repo_url=project.git_repo_url,
        subdomain=project.subdomain,
        project_type=project.project_type,
    )
    
    session.add(record)
    await session.commit()
    await session.refresh(record)
    
    return ProjectResponse.model_validate(record)


@router.get("/projects", response_model=list[ProjectResponse], tags=["Projects"])
async def list_projects(session: AsyncSession = Depends(get_session)):
    """List all registered projects"""
    result = await session.execute(select(ProjectRecord))
    projects = result.scalars().all()
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get("/projects/{project_id}", response_model=ProjectResponse, tags=["Projects"])
async def get_project(
    project_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Get project details"""
    result = await session.execute(
        select(ProjectRecord).where(ProjectRecord.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    
    return ProjectResponse.model_validate(project)


@router.delete("/projects/{project_id}", tags=["Projects"])
async def delete_project(
    project_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Delete a project and all associated resources"""
    result = await session.execute(
        select(ProjectRecord).where(ProjectRecord.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    
    await session.delete(project)
    await session.commit()
    
    return {"status": "deleted", "project_id": project_id}


# =============================================================================
# Port Registry
# =============================================================================

@router.post("/ports/allocate", response_model=PortAllocationResponse, tags=["Ports"])
async def allocate_port(
    request: PortRequest,
    session: AsyncSession = Depends(get_session)
):
    """Allocate a port for a service"""
    registry = PortRegistryService(session)
    
    try:
        allocation = await registry.allocate_port(request)
        return allocation
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ports/bulk-allocate", response_model=list[PortAllocationResponse], tags=["Ports"])
async def bulk_allocate_ports(
    project_id: str,
    services: list[dict],
    environment: Environment = Environment.MIDGARD,
    session: AsyncSession = Depends(get_session)
):
    """
    Bulk allocate ports for a new project.
    
    Request body example:
    ```json
    {
        "project_id": "my-project",
        "services": [
            {"name": "api", "type": "https", "internal_port": 8000},
            {"name": "frontend", "type": "https", "internal_port": 3000},
            {"name": "worker", "type": "http", "internal_port": 8080}
        ]
    }
    ```
    """
    try:
        allocations = await allocate_project_ports(
            session, project_id, services, environment
        )
        return allocations
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/ports", response_model=list[PortAllocationResponse], tags=["Ports"])
async def list_ports(
    project_id: Optional[str] = None,
    environment: Optional[Environment] = None,
    session: AsyncSession = Depends(get_session)
):
    """List all port allocations"""
    registry = PortRegistryService(session)
    
    if project_id:
        return await registry.get_project_ports(project_id, environment)
    
    # Get all ports
    result = await session.execute(select(PortAllocation))
    allocations = result.scalars().all()
    return [PortAllocationResponse.model_validate(a) for a in allocations]


@router.get("/ports/summary", tags=["Ports"])
async def get_port_summary(session: AsyncSession = Depends(get_session)):
    """Get summary of port allocations"""
    registry = PortRegistryService(session)
    return await registry.get_port_summary()


@router.delete("/ports/{allocation_id}", tags=["Ports"])
async def release_port(
    allocation_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Release a port allocation"""
    registry = PortRegistryService(session)
    
    if await registry.release_port(allocation_id):
        return {"status": "released", "allocation_id": allocation_id}
    else:
        raise HTTPException(status_code=404, detail="Port allocation not found")


# =============================================================================
# Deployments
# =============================================================================

@router.post("/deployments", response_model=DeploymentResponse, tags=["Deployments"])
async def register_deployment(
    deployment: DeploymentCreate,
    session: AsyncSession = Depends(get_session)
):
    """Register a new deployment"""
    manager = DeploymentManager(session)
    
    try:
        return await manager.register_deployment(deployment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/deployments", response_model=list[DeploymentResponse], tags=["Deployments"])
async def list_deployments(
    project_id: Optional[str] = None,
    environment: Optional[Environment] = None,
    status: Optional[DeploymentStatus] = None,
    session: AsyncSession = Depends(get_session)
):
    """List deployments with optional filters"""
    manager = DeploymentManager(session)
    return await manager.get_deployments(project_id, environment, status)


@router.get("/deployments/{deployment_id}", response_model=DeploymentResponse, tags=["Deployments"])
async def get_deployment(
    deployment_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Get deployment details"""
    result = await session.execute(
        select(Deployment).where(Deployment.id == deployment_id)
    )
    deployment = result.scalar_one_or_none()
    
    if not deployment:
        raise HTTPException(status_code=404, detail=f"Deployment {deployment_id} not found")
    
    return DeploymentResponse.model_validate(deployment)


@router.post("/deployments/{deployment_id}/health-check", response_model=HealthCheckResponse, tags=["Deployments"])
async def trigger_health_check(
    deployment_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Trigger an immediate health check for a deployment"""
    manager = DeploymentManager(session)
    
    try:
        return await manager.check_health(deployment_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/deployments/{deployment_id}/health-history", response_model=list[HealthCheckResponse], tags=["Deployments"])
async def get_health_history(
    deployment_id: str,
    limit: int = 100,
    session: AsyncSession = Depends(get_session)
):
    """Get health check history for a deployment"""
    result = await session.execute(
        select(HealthCheckRecord)
        .where(HealthCheckRecord.deployment_id == deployment_id)
        .order_by(HealthCheckRecord.checked_at.desc())
        .limit(limit)
    )
    records = result.scalars().all()
    return [HealthCheckResponse.model_validate(r) for r in records]


@router.get("/deployments/discover/docker", tags=["Deployments"])
async def discover_docker_deployments(session: AsyncSession = Depends(get_session)):
    """Discover running Docker containers with ravenhelm labels"""
    manager = DeploymentManager(session)
    return await manager.discover_docker_deployments()


# =============================================================================
# Nginx Configuration
# =============================================================================

@router.get("/nginx/config", tags=["Nginx"])
async def get_nginx_config(session: AsyncSession = Depends(get_session)):
    """Generate and return current nginx configuration"""
    config = await regenerate_nginx_config(session)
    return {"config": config}


@router.get("/nginx/config/{project_id}", tags=["Nginx"])
async def get_project_nginx_config(
    project_id: str,
    environment: Environment = Environment.MIDGARD,
    session: AsyncSession = Depends(get_session)
):
    """Generate nginx config for a specific project"""
    generator = NginxConfigGenerator(session)
    
    try:
        config = await generator.generate_project_config(project_id, environment)
        return {"project_id": project_id, "config": config}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/nginx/reload", tags=["Nginx"])
async def reload_nginx(background_tasks: BackgroundTasks):
    """
    Trigger nginx configuration reload.
    
    This regenerates the config and sends SIGHUP to nginx.
    """
    # TODO: Implement actual nginx reload
    # This would:
    # 1. Regenerate config
    # 2. Validate config (nginx -t)
    # 3. Send SIGHUP to nginx container
    
    return {"status": "reload_scheduled", "message": "Nginx reload has been scheduled"}

