"""
Project Generator Service
Orchestrates the full project scaffolding flow:

1. Create GitLab project from template
2. Allocate ports from registry
3. Generate .hlidskjalf.yaml manifest
4. Generate docker-compose.yml
5. Commit files to GitLab repo
6. Update Traefik routing
7. Create database
8. Register in local database
"""

import asyncio
import base64
from pathlib import Path
from typing import Optional
from datetime import datetime

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.registry import (
    ProjectRecord,
    Service,
    ServiceType,
    ProjectCategory,
    Realm,
    ProjectScaffoldRequest,
    ProjectManifest,
)
from src.services.port_allocator import PortAllocator
from src.services.compose_generator import ComposeGenerator, ManifestGenerator
from src.services.traefik_generator import TraefikGenerator, add_cors_origin_to_middleware
from src.core.config import get_settings

logger = structlog.get_logger(__name__)


# Template project IDs in GitLab (configure these in settings)
TEMPLATE_PROJECT_IDS = {
    "ravenmaskos": None,  # Will be looked up by path
    "platform-template": None,
}


class ProjectGeneratorError(Exception):
    """Raised when project generation fails"""
    pass


class ProjectGenerator:
    """
    Orchestrates the complete project scaffolding workflow.
    
    Creates a new project with:
    - GitLab repository from template
    - Port allocations
    - Manifest and compose files
    - Traefik routing
    - Database setup
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
        
        self.gitlab_api_url = gitlab_url or settings.GITLAB_API_URL or "http://gitlab"
        self.gitlab_external_url = settings.GITLAB_BASE_URL or "https://gitlab.ravenhelm.test"
        self.gitlab_token = gitlab_token or settings.GITLAB_TOKEN
        self.verify_ssl = verify_ssl
        
        self._client: Optional[httpx.AsyncClient] = None
        
        # Paths
        self.traefik_dynamic_yml = Path("ravenhelm-proxy/dynamic.yml")
        self.port_registry_path = Path("config/port_registry.yaml")
    
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
                timeout=60.0
            )
        return self._client
    
    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _get_template_project_id(self, template_name: str) -> Optional[int]:
        """Look up template project ID by name"""
        if TEMPLATE_PROJECT_IDS.get(template_name):
            return TEMPLATE_PROJECT_IDS[template_name]
        
        client = await self._get_client()
        
        try:
            # Search for template in ravenhelm group
            template_path = f"ravenhelm/{template_name}"
            response = await client.get(
                f"/api/v4/projects/{template_path.replace('/', '%2F')}"
            )
            
            if response.status_code == 200:
                project = response.json()
                TEMPLATE_PROJECT_IDS[template_name] = project["id"]
                return project["id"]
            
            # Try templates subgroup
            template_path = f"ravenhelm/templates/{template_name}"
            response = await client.get(
                f"/api/v4/projects/{template_path.replace('/', '%2F')}"
            )
            
            if response.status_code == 200:
                project = response.json()
                TEMPLATE_PROJECT_IDS[template_name] = project["id"]
                return project["id"]
                
        except Exception as e:
            logger.warning("Failed to find template", template=template_name, error=str(e))
        
        return None
    
    async def create_gitlab_project(
        self,
        name: str,
        group_path: str,
        description: Optional[str] = None,
        template_name: Optional[str] = None
    ) -> dict:
        """
        Create a new GitLab project, optionally from a template.
        
        Args:
            name: Project name
            group_path: GitLab group path
            description: Project description
            template_name: Template to use (ravenmaskos, platform-template)
            
        Returns:
            GitLab project data
        """
        client = await self._get_client()
        
        # Get group ID
        response = await client.get(f"/api/v4/groups/{group_path}")
        if response.status_code != 200:
            raise ProjectGeneratorError(f"Group '{group_path}' not found")
        
        group = response.json()
        
        # Build project creation payload
        payload = {
            "name": name,
            "path": name.lower().replace(" ", "-"),
            "namespace_id": group["id"],
            "visibility": "private",
            "initialize_with_readme": True
        }
        
        if description:
            payload["description"] = description
        
        # Use template if specified
        if template_name:
            template_id = await self._get_template_project_id(template_name)
            if template_id:
                payload["use_custom_template"] = True
                payload["template_project_id"] = template_id
                logger.info("Using template", template=template_name, id=template_id)
        
        # Create project
        response = await client.post("/api/v4/projects", json=payload)
        
        if response.status_code not in (200, 201):
            error = response.json().get("message", response.text)
            raise ProjectGeneratorError(f"Failed to create GitLab project: {error}")
        
        project = response.json()
        
        # Convert internal URL to external
        web_url = project.get("web_url", "")
        if self.gitlab_api_url in web_url:
            project["web_url"] = web_url.replace(
                self.gitlab_api_url,
                self.gitlab_external_url
            )
        
        logger.info(
            "Created GitLab project",
            name=name,
            id=project["id"],
            web_url=project["web_url"]
        )
        
        return project
    
    async def commit_file_to_gitlab(
        self,
        project_id: int,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str = "main"
    ) -> bool:
        """
        Commit a file to a GitLab repository.
        
        Args:
            project_id: GitLab project ID
            file_path: Path within the repository
            content: File content
            commit_message: Commit message
            branch: Target branch
            
        Returns:
            True if successful
        """
        client = await self._get_client()
        
        # Check if file exists
        encoded_path = file_path.replace("/", "%2F")
        response = await client.get(
            f"/api/v4/projects/{project_id}/repository/files/{encoded_path}",
            params={"ref": branch}
        )
        
        action = "update" if response.status_code == 200 else "create"
        
        # Commit the file
        payload = {
            "branch": branch,
            "commit_message": commit_message,
            "actions": [
                {
                    "action": action,
                    "file_path": file_path,
                    "content": content
                }
            ]
        }
        
        response = await client.post(
            f"/api/v4/projects/{project_id}/repository/commits",
            json=payload
        )
        
        if response.status_code not in (200, 201):
            logger.error(
                "Failed to commit file",
                project_id=project_id,
                file_path=file_path,
                error=response.text
            )
            return False
        
        logger.info(
            "Committed file to GitLab",
            project_id=project_id,
            file_path=file_path,
            action=action
        )
        
        return True
    
    async def create_database(self, db_name: str) -> bool:
        """
        Create a new database in shared PostgreSQL.
        
        Args:
            db_name: Database name (will be sanitized)
            
        Returns:
            True if successful
        """
        # Note: This requires psycopg2 or asyncpg with admin privileges
        # For now, we'll log the required SQL
        sanitized_name = db_name.replace("-", "_").lower()
        
        logger.info(
            "Database creation required",
            db_name=sanitized_name,
            sql=f"CREATE DATABASE {sanitized_name}; GRANT ALL ON DATABASE {sanitized_name} TO postgres;"
        )
        
        # TODO: Execute via database admin connection
        # This would require a separate admin session with CREATE DATABASE privileges
        
        return True
    
    async def scaffold_project(
        self,
        request: ProjectScaffoldRequest
    ) -> ProjectRecord:
        """
        Execute the complete project scaffolding workflow.
        
        Args:
            request: Project scaffold request with all options
            
        Returns:
            Created ProjectRecord
        """
        project_id = request.name.lower().replace(" ", "-")
        gitlab_path = f"{request.group}/{project_id}"
        
        logger.info(
            "Starting project scaffold",
            name=request.name,
            category=request.category.value,
            realm=request.realm.value
        )
        
        try:
            # Step 1: Allocate ports
            port_allocator = PortAllocator(self.db, self.port_registry_path)
            
            services_to_allocate = []
            if request.include_api:
                services_to_allocate.append("api")
            if request.include_ui:
                services_to_allocate.append("ui")
            if request.include_worker:
                services_to_allocate.append("worker")
            
            if not services_to_allocate:
                raise ProjectGeneratorError("At least one service must be included")
            
            allocated_ports = await port_allocator.allocate_ports(
                project_id=project_id,
                category=request.category,
                services=services_to_allocate,
                environment=request.realm
            )
            
            api_port = allocated_ports.get("api", 0)
            ui_port = allocated_ports.get("ui", 0)
            
            logger.info(
                "Ports allocated",
                project_id=project_id,
                ports=allocated_ports
            )
            
            # Step 2: Create GitLab project
            gitlab_project = await self.create_gitlab_project(
                name=request.name,
                group_path=request.group,
                description=request.description,
                template_name=request.template
            )
            
            # Step 3: Generate manifest
            manifest_gen = ManifestGenerator(project_id, request.name)
            manifest = manifest_gen.generate(
                gitlab_path=gitlab_path,
                category=request.category,
                realm=request.realm,
                api_port=api_port,
                ui_port=ui_port,
                include_api=request.include_api,
                include_ui=request.include_ui,
                include_worker=request.include_worker,
                use_postgres=request.use_postgres,
                use_redis=request.use_redis,
                use_nats=request.use_nats,
                use_livekit=request.use_livekit,
                isolated_network=request.isolated_network
            )
            manifest_yaml = manifest_gen.generate_yaml(
                gitlab_path=gitlab_path,
                category=request.category,
                realm=request.realm,
                api_port=api_port,
                ui_port=ui_port,
                include_api=request.include_api,
                include_ui=request.include_ui,
                include_worker=request.include_worker,
                use_postgres=request.use_postgres,
                use_redis=request.use_redis,
                use_nats=request.use_nats,
                use_livekit=request.use_livekit,
                isolated_network=request.isolated_network
            )
            
            # Step 4: Generate docker-compose.yml
            compose_gen = ComposeGenerator(project_id, request.name)
            compose_yaml = compose_gen.generate_yaml(manifest, gitlab_path)
            
            # Step 5: Commit files to GitLab
            await self.commit_file_to_gitlab(
                project_id=gitlab_project["id"],
                file_path=".hlidskjalf.yaml",
                content=manifest_yaml,
                commit_message="[Hlidskjalf] Add project manifest"
            )
            
            await self.commit_file_to_gitlab(
                project_id=gitlab_project["id"],
                file_path="docker-compose.yml",
                content=compose_yaml,
                commit_message="[Hlidskjalf] Add docker-compose configuration"
            )
            
            # Step 6: Update Traefik routing
            traefik_gen = TraefikGenerator(project_id, request.name)
            if self.traefik_dynamic_yml.exists():
                traefik_gen.update_dynamic_yml(
                    manifest,
                    self.traefik_dynamic_yml,
                    request.realm
                )
                
                # Add CORS origin
                cors_origin = traefik_gen.generate_cors_origin(request.realm)
                add_cors_origin_to_middleware(
                    self.traefik_dynamic_yml,
                    cors_origin
                )
            
            # Step 7: Update port registry
            port_allocator.add_project_to_registry(
                project_id=project_id,
                category=request.category,
                api_port=api_port,
                ui_port=ui_port,
                domain=f"{project_id}.ravenhelm.test",
                realm=request.realm,
                description=request.description or f"Auto-generated: {request.name}",
                git_remote="gitlab.ravenhelm.test"
            )
            
            # Step 8: Create database if needed
            if request.use_postgres:
                await self.create_database(project_id)
            
            # Step 9: Create local project record
            subdomain = project_id
            
            # Check for subdomain conflict
            result = await self.db.execute(
                select(ProjectRecord).where(
                    ProjectRecord.subdomain == subdomain
                )
            )
            if result.scalar_one_or_none():
                subdomain = f"{subdomain}-{gitlab_project['id']}"
            
            project_record = ProjectRecord(
                id=project_id,
                name=request.name,
                description=request.description,
                git_repo_url=gitlab_project["web_url"],
                git_branch=gitlab_project.get("default_branch", "main"),
                gitlab_id=gitlab_project["id"],
                gitlab_path=gitlab_path,
                gitlab_web_url=gitlab_project["web_url"],
                gitlab_default_branch=gitlab_project.get("default_branch", "main"),
                synced_at=datetime.utcnow(),
                subdomain=subdomain,
                category=request.category,
                realm=request.realm
            )
            self.db.add(project_record)
            
            # Step 10: Create service records
            for svc in manifest.services:
                service = Service(
                    id=f"{project_id}/{svc.name}",
                    project_id=project_id,
                    name=svc.name,
                    service_type=svc.type,
                    port=svc.port,
                    internal_port=svc.internal_port,
                    health_check_path=svc.health_check,
                    compose_service=svc.compose_service,
                    container_name=f"gitlab-sre-{project_id}-{svc.name}",
                    domain=f"{project_id}-{svc.name}.ravenhelm.test" if svc.type != ServiceType.FRONTEND else f"{project_id}.ravenhelm.test"
                )
                self.db.add(service)
            
            await self.db.commit()
            await self.db.refresh(project_record)
            
            logger.info(
                "Project scaffolding complete",
                project_id=project_id,
                gitlab_url=gitlab_project["web_url"],
                services=[svc.name for svc in manifest.services]
            )
            
            return project_record
            
        except Exception as e:
            logger.error(
                "Project scaffolding failed",
                name=request.name,
                error=str(e),
                exc_info=True
            )
            raise ProjectGeneratorError(f"Failed to scaffold project: {str(e)}")

