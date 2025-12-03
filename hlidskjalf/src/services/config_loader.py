"""
Configuration Loader Service
Loads port_registry.yaml and seeds the database with project and port information.

The ravens bring knowledge from the YAML scrolls into the living registry.
"""

from pathlib import Path
from typing import Optional
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.models.registry import (
    ProjectRecord,
    PortAllocation,
    PortType,
    Realm,
)

logger = get_logger(__name__)


def expand_path(path: str) -> Path:
    """Expand ~ and environment variables in path"""
    return Path(path).expanduser()


class ConfigLoader:
    """
    Loads platform configuration from YAML files.
    
    The YAML config is the source of truth for project inventory,
    while the database tracks runtime state (deployments, health).
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            repo_root = Path(__file__).resolve().parents[3]
            package_root = Path(__file__).resolve().parents[2]
            candidate_paths = [
                repo_root / "config" / "port_registry.yaml",
                package_root / "config" / "port_registry.yaml",
            ]
            for candidate in candidate_paths:
                if candidate.exists():
                    config_path = candidate
                    break
            else:
                config_path = candidate_paths[0]
        
        self.config_path = config_path
        self._config: Optional[dict] = None
    
    def load_config(self) -> dict:
        """Load and parse the YAML configuration"""
        if self._config is None:
            if not self.config_path.exists():
                raise FileNotFoundError(f"Config file not found: {self.config_path}")
            
            with open(self.config_path) as f:
                self._config = yaml.safe_load(f)
            
            logger.info("Configuration loaded", path=str(self.config_path))
        
        return self._config
    
    @property
    def config(self) -> dict:
        return self.load_config()
    
    def get_reserved_ports(self) -> list[int]:
        """Get list of reserved ports that should never be auto-assigned"""
        return [p["port"] for p in self.config.get("reserved", [])]
    
    def get_port_range(self, range_name: str) -> tuple[int, int]:
        """Get start and end ports for a named range"""
        ranges = self.config.get("ranges", {})
        if range_name not in ranges:
            raise ValueError(f"Unknown port range: {range_name}")
        
        r = ranges[range_name]
        return r["start"], r["end"]
    
    def get_next_available_port(self, range_name: str) -> int:
        """Get the next available port from next_available tracking"""
        key_map = {
            "personal_api": "personal_api",
            "personal_ui": "personal_ui",
            "work_api": "work_api",
            "work_ui": "work_ui",
            "sandbox_api": "sandbox_api",
            "sandbox_ui": "sandbox_ui",
        }
        
        next_available = self.config.get("next_available", {})
        return next_available.get(key_map.get(range_name, range_name), 8000)
    
    def get_all_projects(self) -> list[dict]:
        """Get all projects from personal and work sections"""
        projects = []
        
        # Platform services
        for name, details in self.config.get("platform", {}).items():
            projects.append({
                "id": name,
                "name": name,
                "type": "platform",
                "realm": "vanaheim",
                "git_remote": None,
                **details
            })
        
        # Personal projects
        for name, details in self.config.get("personal", {}).items():
            projects.append({
                "id": name,
                "name": name,
                "type": "personal",
                **details
            })
        
        # Work projects
        for name, details in self.config.get("work", {}).items():
            projects.append({
                "id": name,
                "name": name,
                "type": "work",
                **details
            })
        
        return projects
    
    async def sync_to_database(self, session: AsyncSession) -> dict:
        """
        Sync configuration to database.
        Creates/updates projects and port allocations from YAML.
        
        Returns summary of changes.
        """
        summary = {
            "projects_created": 0,
            "projects_updated": 0,
            "ports_created": 0,
            "errors": []
        }
        
        projects = self.get_all_projects()
        
        for project_config in projects:
            try:
                # Check if project exists
                result = await session.execute(
                    select(ProjectRecord).where(
                        ProjectRecord.id == project_config["id"]
                    )
                )
                existing = result.scalar_one_or_none()
                
                # Extract domain for subdomain
                domain = project_config.get("domain", f"{project_config['id']}.ravenhelm.test")
                subdomain = domain.replace(".ravenhelm.test", "")
                
                if existing:
                    # Update existing project
                    existing.name = project_config.get("name", existing.name)
                    existing.description = project_config.get("description", existing.description)
                    summary["projects_updated"] += 1
                else:
                    # Create new project
                    project = ProjectRecord(
                        id=project_config["id"],
                        name=project_config.get("name", project_config["id"]),
                        description=project_config.get("description"),
                        subdomain=subdomain,
                        project_type=project_config.get("type", "application"),
                        git_repo_url=self._build_git_url(project_config),
                    )
                    session.add(project)
                    summary["projects_created"] += 1
                    logger.info("Project created", project_id=project_config["id"])
                
                # Sync port allocations
                ports_created = await self._sync_ports(
                    session,
                    project_config
                )
                summary["ports_created"] += ports_created
                
            except Exception as e:
                error_msg = f"Error syncing project {project_config['id']}: {str(e)}"
                summary["errors"].append(error_msg)
                logger.error(error_msg, exc_info=True)
        
        await session.commit()
        
        logger.info(
            "Configuration sync complete",
            projects_created=summary["projects_created"],
            projects_updated=summary["projects_updated"],
            ports_created=summary["ports_created"],
            errors=len(summary["errors"])
        )
        
        return summary
    
    async def _sync_ports(
        self,
        session: AsyncSession,
        project_config: dict
    ) -> int:
        """Sync port allocations for a project"""
        created = 0
        project_id = project_config["id"]
        
        # Main API port
        if "api_port" in project_config:
            created += await self._ensure_port(
                session,
                project_id,
                "api",
                project_config["api_port"],
                PortType.HTTPS
            )
        
        # Main UI port
        if "ui_port" in project_config:
            created += await self._ensure_port(
                session,
                project_id,
                "frontend",
                project_config["ui_port"],
                PortType.HTTPS
            )
        
        # Additional services
        for service in project_config.get("services", []):
            port_type = PortType.HTTPS
            if "grpc" in service.get("name", "").lower():
                port_type = PortType.GRPC
            elif "metrics" in service.get("name", "").lower():
                port_type = PortType.METRICS
            
            created += await self._ensure_port(
                session,
                project_id,
                service["name"],
                service["port"],
                port_type
            )
        
        return created
    
    async def _ensure_port(
        self,
        session: AsyncSession,
        project_id: str,
        service_name: str,
        port: int,
        port_type: PortType
    ) -> int:
        """Ensure a port allocation exists, create if not"""
        # Check if exists
        result = await session.execute(
            select(PortAllocation).where(
                PortAllocation.project_id == project_id,
                PortAllocation.service_name == service_name,
                PortAllocation.environment == Realm.MIDGARD  # Dev
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update if port changed
            if existing.port != port:
                existing.port = port
            return 0
        
        # Create new allocation
        allocation = PortAllocation(
            project_id=project_id,
            service_name=service_name,
            port=port,
            port_type=port_type,
            environment=Realm.MIDGARD,
            auto_assigned=False,  # From config
            description=f"From port_registry.yaml"
        )
        session.add(allocation)
        return 1
    
    def _build_git_url(self, project_config: dict) -> Optional[str]:
        """Build git URL based on remote type"""
        git_remote = project_config.get("git_remote")
        path = project_config.get("path")
        
        if not git_remote or not path:
            return None
        
        # Extract project name from path
        project_name = Path(path).name
        
        if git_remote == "github.com-quant":
            return f"git@github.com-quant:quant/{project_name}.git"
        elif git_remote == "github.com-nwalker":
            return f"git@github.com-nwalker:nwalker85/{project_name}.git"
        
        return None


async def load_and_sync_config(
    session: AsyncSession,
    config_path: Optional[Path] = None
) -> dict:
    """
    Convenience function to load config and sync to database.
    Call this on startup to ensure database matches configuration.
    """
    loader = ConfigLoader(config_path)
    return await loader.sync_to_database(session)


def get_config_loader(config_path: Optional[Path] = None) -> ConfigLoader:
    """Get a ConfigLoader instance"""
    return ConfigLoader(config_path)

