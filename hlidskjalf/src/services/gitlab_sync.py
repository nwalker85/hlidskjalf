"""
GitLab Sync Service
Synchronizes projects from GitLab to the Hlidskjalf platform.

Responsibilities:
- Fetch projects from GitLab groups
- Parse .hlidskjalf.yaml manifests
- Create/update local project and service records
- Background sync job
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
import base64

import httpx
import structlog
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.registry import (
    ProjectRecord,
    Service,
    ServiceType,
    ProjectCategory,
    Realm,
    ProjectManifest,
    ManifestServiceConfig,
)
from src.core.config import get_settings

logger = structlog.get_logger(__name__)


class GitLabSyncService:
    """
    Synchronizes projects from GitLab to the local database.
    
    Connects to GitLab API, fetches project metadata and manifests,
    and keeps local records in sync.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        gitlab_url: Optional[str] = None,
        gitlab_token: Optional[str] = None,
        verify_ssl: bool = False
    ):
        self.db = db
        settings = get_settings()
        
        # Use internal URL for speed, external for web_url generation
        self.gitlab_api_url = gitlab_url or settings.GITLAB_API_URL or "http://gitlab"
        self.gitlab_external_url = settings.GITLAB_BASE_URL or "https://gitlab.ravenhelm.test"
        self.gitlab_token = gitlab_token or settings.GITLAB_TOKEN
        self.verify_ssl = verify_ssl
        
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.gitlab_api_url,
                headers={
                    "PRIVATE-TOKEN": self.gitlab_token,
                    "Content-Type": "application/json"
                },
                verify=self.verify_ssl,
                timeout=30.0
            )
        return self._client
    
    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def fetch_group_projects(
        self,
        group_path: str = "ravenhelm",
        include_subgroups: bool = True
    ) -> list[dict]:
        """
        Fetch all projects from a GitLab group.
        
        Args:
            group_path: GitLab group path (e.g., "ravenhelm")
            include_subgroups: Include projects from subgroups
            
        Returns:
            List of project dictionaries from GitLab API
        """
        client = await self._get_client()
        projects = []
        page = 1
        
        try:
            while True:
                response = await client.get(
                    f"/api/v4/groups/{group_path}/projects",
                    params={
                        "include_subgroups": str(include_subgroups).lower(),
                        "per_page": 100,
                        "page": page,
                        "order_by": "last_activity_at",
                        "sort": "desc"
                    }
                )
                response.raise_for_status()
                
                page_projects = response.json()
                if not page_projects:
                    break
                
                projects.extend(page_projects)
                page += 1
                
                # Safety limit
                if page > 100:
                    logger.warning("Hit pagination limit", group=group_path)
                    break
            
            logger.info(
                "Fetched GitLab projects",
                group=group_path,
                count=len(projects)
            )
            return projects
            
        except httpx.HTTPError as e:
            logger.error("Failed to fetch GitLab projects", error=str(e))
            raise
    
    async def fetch_project_file(
        self,
        project_id: int,
        file_path: str,
        ref: str = "main"
    ) -> Optional[str]:
        """
        Fetch a file from a GitLab project repository.
        
        Args:
            project_id: GitLab project ID
            file_path: Path to file in repository
            ref: Branch or tag (default: main)
            
        Returns:
            File contents as string, or None if not found
        """
        client = await self._get_client()
        
        try:
            # URL-encode the file path
            encoded_path = file_path.replace("/", "%2F")
            
            response = await client.get(
                f"/api/v4/projects/{project_id}/repository/files/{encoded_path}",
                params={"ref": ref}
            )
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # GitLab returns base64-encoded content
            content = base64.b64decode(data["content"]).decode("utf-8")
            return content
            
        except httpx.HTTPError as e:
            logger.debug(
                "Failed to fetch file",
                project_id=project_id,
                file_path=file_path,
                error=str(e)
            )
            return None
    
    async def fetch_manifest(
        self,
        project_id: int,
        default_branch: str = "main"
    ) -> Optional[ProjectManifest]:
        """
        Fetch and parse .hlidskjalf.yaml manifest from a project.
        
        Args:
            project_id: GitLab project ID
            default_branch: Branch to fetch from
            
        Returns:
            Parsed ProjectManifest or None if not found
        """
        content = await self.fetch_project_file(
            project_id,
            ".hlidskjalf.yaml",
            ref=default_branch
        )
        
        if not content:
            return None
        
        try:
            data = yaml.safe_load(content)
            return ProjectManifest(**data)
        except Exception as e:
            logger.warning(
                "Failed to parse manifest",
                project_id=project_id,
                error=str(e)
            )
            return None
    
    def _parse_category(self, gitlab_path: str) -> ProjectCategory:
        """Determine project category from GitLab path"""
        path_lower = gitlab_path.lower()
        
        if "personal" in path_lower or "nwalker" in path_lower:
            return ProjectCategory.PERSONAL
        elif "work" in path_lower or "quant" in path_lower:
            return ProjectCategory.WORK
        elif "sandbox" in path_lower or "test" in path_lower:
            return ProjectCategory.SANDBOX
        else:
            return ProjectCategory.PLATFORM
    
    async def sync_project(
        self,
        gitlab_project: dict
    ) -> Optional[ProjectRecord]:
        """
        Sync a single GitLab project to the local database.
        
        Args:
            gitlab_project: Project data from GitLab API
            
        Returns:
            Created or updated ProjectRecord
        """
        gitlab_id = gitlab_project["id"]
        gitlab_path = gitlab_project["path_with_namespace"]
        name = gitlab_project["name"]
        
        # Check if project already exists
        result = await self.db.execute(
            select(ProjectRecord).where(
                ProjectRecord.gitlab_id == gitlab_id
            )
        )
        existing = result.scalar_one_or_none()
        
        # Generate subdomain from path
        subdomain = gitlab_path.replace("/", "-").lower()
        
        # Parse last activity
        last_activity = None
        if gitlab_project.get("last_activity_at"):
            try:
                last_activity = datetime.fromisoformat(
                    gitlab_project["last_activity_at"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass
        
        # Convert internal URL to external URL
        web_url = gitlab_project.get("web_url", "")
        if self.gitlab_api_url in web_url:
            web_url = web_url.replace(
                self.gitlab_api_url,
                self.gitlab_external_url
            )
        
        if existing:
            # Update existing project
            existing.name = name
            existing.description = gitlab_project.get("description")
            existing.gitlab_path = gitlab_path
            existing.gitlab_web_url = web_url
            existing.gitlab_default_branch = gitlab_project.get("default_branch", "main")
            existing.gitlab_last_activity = last_activity
            existing.synced_at = datetime.utcnow()
            
            project = existing
            logger.debug("Updated project", gitlab_path=gitlab_path)
        else:
            # Check if subdomain conflicts
            result = await self.db.execute(
                select(ProjectRecord).where(
                    ProjectRecord.subdomain == subdomain
                )
            )
            if result.scalar_one_or_none():
                # Add suffix to make unique
                subdomain = f"{subdomain}-{gitlab_id}"
            
            # Create new project
            project = ProjectRecord(
                id=subdomain,
                name=name,
                description=gitlab_project.get("description"),
                git_repo_url=web_url,
                git_branch=gitlab_project.get("default_branch", "main"),
                gitlab_id=gitlab_id,
                gitlab_path=gitlab_path,
                gitlab_web_url=web_url,
                gitlab_default_branch=gitlab_project.get("default_branch", "main"),
                gitlab_last_activity=last_activity,
                synced_at=datetime.utcnow(),
                subdomain=subdomain,
                category=self._parse_category(gitlab_path),
                realm=Realm.MIDGARD
            )
            self.db.add(project)
            logger.info("Created project", gitlab_path=gitlab_path, id=subdomain)
        
        return project
    
    async def sync_services_from_manifest(
        self,
        project: ProjectRecord,
        manifest: ProjectManifest
    ) -> list[Service]:
        """
        Sync services from manifest to database.
        
        Args:
            project: The parent project
            manifest: Parsed manifest
            
        Returns:
            List of created/updated Service records
        """
        services = []
        
        for svc_config in manifest.services:
            service_id = f"{project.id}/{svc_config.name}"
            
            # Check if service exists
            result = await self.db.execute(
                select(Service).where(Service.id == service_id)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing
                existing.port = svc_config.port
                existing.internal_port = svc_config.internal_port
                existing.health_check_path = svc_config.health_check
                existing.compose_service = svc_config.compose_service
                service = existing
            else:
                # Create new
                service = Service(
                    id=service_id,
                    project_id=project.id,
                    name=svc_config.name,
                    service_type=svc_config.type,
                    port=svc_config.port,
                    internal_port=svc_config.internal_port,
                    health_check_path=svc_config.health_check,
                    compose_service=svc_config.compose_service,
                    container_name=f"gitlab-sre-{project.id}-{svc_config.name}",
                    domain=f"{project.id}-{svc_config.name}.ravenhelm.test"
                )
                self.db.add(service)
            
            services.append(service)
            logger.debug(
                "Synced service",
                project_id=project.id,
                service=svc_config.name
            )
        
        return services
    
    async def sync_all(
        self,
        group_path: str = "ravenhelm"
    ) -> dict:
        """
        Full sync of all projects from GitLab.
        
        Args:
            group_path: GitLab group to sync
            
        Returns:
            Summary of sync results
        """
        summary = {
            "projects_synced": 0,
            "projects_created": 0,
            "projects_updated": 0,
            "services_synced": 0,
            "manifests_found": 0,
            "errors": []
        }
        
        try:
            gitlab_projects = await self.fetch_group_projects(group_path)
            
            for gitlab_project in gitlab_projects:
                try:
                    # Check if this is an update or create
                    result = await self.db.execute(
                        select(ProjectRecord).where(
                            ProjectRecord.gitlab_id == gitlab_project["id"]
                        )
                    )
                    is_new = result.scalar_one_or_none() is None
                    
                    # Sync project
                    project = await self.sync_project(gitlab_project)
                    if project:
                        summary["projects_synced"] += 1
                        if is_new:
                            summary["projects_created"] += 1
                        else:
                            summary["projects_updated"] += 1
                        
                        # Try to fetch and sync manifest
                        manifest = await self.fetch_manifest(
                            gitlab_project["id"],
                            gitlab_project.get("default_branch", "main")
                        )
                        
                        if manifest:
                            summary["manifests_found"] += 1
                            services = await self.sync_services_from_manifest(
                                project, manifest
                            )
                            summary["services_synced"] += len(services)
                        
                except Exception as e:
                    error_msg = f"Error syncing {gitlab_project.get('path_with_namespace')}: {str(e)}"
                    summary["errors"].append(error_msg)
                    logger.error(error_msg, exc_info=True)
            
            await self.db.commit()
            
            logger.info(
                "GitLab sync complete",
                projects=summary["projects_synced"],
                services=summary["services_synced"],
                errors=len(summary["errors"])
            )
            
        except Exception as e:
            summary["errors"].append(f"Sync failed: {str(e)}")
            logger.error("GitLab sync failed", error=str(e), exc_info=True)
        
        return summary


class GitLabSyncJob:
    """
    Background job that periodically syncs projects from GitLab.
    """
    
    def __init__(
        self,
        session_factory,
        interval_seconds: int = 300,  # 5 minutes
        group_path: str = "ravenhelm"
    ):
        self.session_factory = session_factory
        self.interval_seconds = interval_seconds
        self.group_path = group_path
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the background sync job"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "GitLab sync job started",
            interval=self.interval_seconds,
            group=self.group_path
        )
    
    async def stop(self):
        """Stop the background sync job"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("GitLab sync job stopped")
    
    async def _run_loop(self):
        """Main sync loop"""
        while self._running:
            try:
                async with self.session_factory() as session:
                    sync_service = GitLabSyncService(session)
                    try:
                        await sync_service.sync_all(self.group_path)
                    finally:
                        await sync_service.close()
                
            except Exception as e:
                logger.error("GitLab sync job error", error=str(e), exc_info=True)
            
            # Wait for next interval
            await asyncio.sleep(self.interval_seconds)
    
    async def trigger_sync(self) -> dict:
        """Manually trigger a sync"""
        async with self.session_factory() as session:
            sync_service = GitLabSyncService(session)
            try:
                return await sync_service.sync_all(self.group_path)
            finally:
                await sync_service.close()

