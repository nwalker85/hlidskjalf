"""
Project Scaffolding API Routes
Endpoints for creating and managing projects with GitLab integration.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from src.api.routes import get_session
from src.models.registry import (
    ProjectRecord,
    Service,
    ProjectScaffoldRequest,
    ProjectResponse,
    ServiceResponse,
    ProjectCategory,
    Realm,
)
from src.services.project_generator import ProjectGenerator, ProjectGeneratorError
from src.services.gitlab_sync import GitLabSyncService
from src.services.port_allocator import PortAllocator

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Project Scaffolding"])


# =============================================================================
# Project Scaffolding
# =============================================================================

@router.post("/projects/scaffold", response_model=ProjectResponse)
async def scaffold_project(
    request: ProjectScaffoldRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Scaffold a new project with full GitLab integration.
    
    This creates:
    - GitLab repository from template
    - Port allocations
    - .hlidskjalf.yaml manifest
    - docker-compose.yml
    - Traefik routing
    - Database (if postgres requested)
    - Local project record
    """
    generator = ProjectGenerator(session)
    
    try:
        project = await generator.scaffold_project(request)
        
        # Reload with relationships
        result = await session.execute(
            select(ProjectRecord)
            .options(selectinload(ProjectRecord.ports))
            .options(selectinload(ProjectRecord.services))
            .where(ProjectRecord.id == project.id)
        )
        project = result.scalar_one()
        
        return ProjectResponse.model_validate(project)
        
    except ProjectGeneratorError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Project scaffold failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to scaffold project: {str(e)}")
    finally:
        await generator.close()


# =============================================================================
# GitLab Sync
# =============================================================================

@router.post("/projects/sync")
async def sync_gitlab_projects(
    group: str = "ravenhelm",
    background_tasks: BackgroundTasks = None,
    session: AsyncSession = Depends(get_session)
):
    """
    Sync projects from GitLab to local database.
    
    Fetches all projects from the specified GitLab group,
    creates/updates local records, and parses .hlidskjalf.yaml
    manifests for service discovery.
    """
    sync_service = GitLabSyncService(session)
    
    try:
        result = await sync_service.sync_all(group)
        return {
            "status": "success",
            "summary": result
        }
    except Exception as e:
        logger.error("GitLab sync failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
    finally:
        await sync_service.close()


@router.get("/projects/{project_id}/sync")
async def sync_single_project(
    project_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Sync a single project from GitLab.
    
    Re-fetches the project metadata and manifest from GitLab
    and updates the local record.
    """
    # Get existing project
    result = await session.execute(
        select(ProjectRecord).where(ProjectRecord.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project or not project.gitlab_id:
        raise HTTPException(status_code=404, detail="Project not found or not linked to GitLab")
    
    sync_service = GitLabSyncService(session)
    
    try:
        # Fetch from GitLab
        client = await sync_service._get_client()
        response = await client.get(f"/api/v4/projects/{project.gitlab_id}")
        
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="GitLab project not found")
        
        gitlab_project = response.json()
        
        # Sync project
        await sync_service.sync_project(gitlab_project)
        
        # Sync manifest
        manifest = await sync_service.fetch_manifest(
            project.gitlab_id,
            gitlab_project.get("default_branch", "main")
        )
        
        if manifest:
            await sync_service.sync_services_from_manifest(project, manifest)
        
        await session.commit()
        
        # Reload
        result = await session.execute(
            select(ProjectRecord)
            .options(selectinload(ProjectRecord.ports))
            .options(selectinload(ProjectRecord.services))
            .where(ProjectRecord.id == project_id)
        )
        project = result.scalar_one()
        
        return ProjectResponse.model_validate(project)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Project sync failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
    finally:
        await sync_service.close()


# =============================================================================
# Services
# =============================================================================

@router.get("/projects/{project_id}/services", response_model=list[ServiceResponse])
async def list_project_services(
    project_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    List all services for a project.
    """
    result = await session.execute(
        select(Service).where(Service.project_id == project_id)
    )
    services = result.scalars().all()
    
    return [ServiceResponse.model_validate(s) for s in services]


@router.get("/services/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Get service details by ID.
    """
    result = await session.execute(
        select(Service).where(Service.id == service_id)
    )
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return ServiceResponse.model_validate(service)


# =============================================================================
# Port Allocation
# =============================================================================

@router.get("/ports/next-available")
async def get_next_available_ports(
    category: ProjectCategory = ProjectCategory.WORK,
    session: AsyncSession = Depends(get_session)
):
    """
    Get the next available ports for a project category.
    
    Returns:
        api_port: Next available API port
        ui_port: Next available UI port
    """
    allocator = PortAllocator(session)
    api_port, ui_port = allocator.get_next_available(category)
    
    return {
        "category": category.value,
        "api_port": api_port,
        "ui_port": ui_port
    }


@router.get("/ports/ranges")
async def get_port_ranges():
    """
    Get the port range configuration for each category.
    """
    from src.services.port_allocator import PORT_RANGES
    
    return {
        category.value: {
            "api_start": range.api_start,
            "api_end": range.api_end,
            "ui_start": range.ui_start,
            "ui_end": range.ui_end
        }
        for category, range in PORT_RANGES.items()
    }


# =============================================================================
# Templates
# =============================================================================

@router.get("/templates")
async def list_templates():
    """
    List available project templates.
    """
    return {
        "templates": [
            {
                "id": "ravenmaskos",
                "name": "RavenmaskOS",
                "description": "Full-stack FastAPI + Next.js template with auth, multi-tenancy, and observability",
                "features": [
                    "FastAPI backend with SQLAlchemy",
                    "Next.js frontend with Tailwind",
                    "Zitadel SSO integration",
                    "OpenTelemetry instrumentation",
                    "Docker + Kubernetes configs",
                    "CI/CD pipeline templates"
                ]
            },
            {
                "id": "platform-template",
                "name": "Platform Template",
                "description": "Minimal CI/CD and Terraform template for infrastructure projects",
                "features": [
                    "GitLab CI/CD templates",
                    "Terraform modules",
                    "Environment separation",
                    "Security scanning"
                ]
            }
        ]
    }


# =============================================================================
# Categories and Realms
# =============================================================================

@router.get("/categories")
async def list_categories():
    """
    List available project categories with their port ranges.
    """
    from src.services.port_allocator import PORT_RANGES
    
    return [
        {
            "id": category.value,
            "name": category.name.title(),
            "api_range": f"{range.api_start}-{range.api_end}",
            "ui_range": f"{range.ui_start}-{range.ui_end}"
        }
        for category, range in PORT_RANGES.items()
    ]


@router.get("/realms")
async def list_realms():
    """
    List available deployment realms (environments).
    """
    realm_descriptions = {
        Realm.MIDGARD: "Development - local Docker environment",
        Realm.ALFHEIM: "Staging - pre-production testing",
        Realm.ASGARD: "Production - live environment",
        Realm.NIFLHEIM: "Disaster Recovery",
        Realm.MUSPELHEIM: "Load Testing / Chaos Engineering",
        Realm.JOTUNHEIM: "Sandbox - experiments",
        Realm.VANAHEIM: "Shared Services - platform infrastructure",
        Realm.SVARTALFHEIM: "Data - databases and analytics",
        Realm.HELHEIM: "Archive - cold storage"
    }
    
    return [
        {
            "id": realm.value,
            "name": realm.name.title(),
            "description": realm_descriptions.get(realm, "")
        }
        for realm in Realm
    ]

