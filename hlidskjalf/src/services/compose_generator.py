"""
Docker Compose Generator
Generates docker-compose.yml files from .hlidskjalf.yaml manifests.

Creates properly configured compose files that:
- Connect to platform_net for shared service access
- Use correct container labels for discovery
- Configure environment variables for shared services
"""

from pathlib import Path
from typing import Optional
import yaml

import structlog

from src.models.registry import (
    ProjectManifest,
    ManifestServiceConfig,
    ServiceType,
    ProjectCategory,
    Realm,
)

logger = structlog.get_logger(__name__)


# Shared service connection strings
SHARED_SERVICE_ENV = {
    "postgres": {
        "DATABASE_URL": "postgresql://postgres:postgres@gitlab-sre-postgres:5432/{db_name}",
        "POSTGRES_HOST": "gitlab-sre-postgres",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "postgres",
    },
    "redis": {
        "REDIS_URL": "redis://gitlab-sre-redis:6379/0",
        "REDIS_HOST": "gitlab-sre-redis",
        "REDIS_PORT": "6379",
    },
    "nats": {
        "NATS_URL": "nats://gitlab-sre-nats:4222",
        "NATS_HOST": "gitlab-sre-nats",
        "NATS_PORT": "4222",
    },
    "redpanda": {
        "KAFKA_BOOTSTRAP_SERVERS": "gitlab-sre-redpanda:9092",
        "SCHEMA_REGISTRY_URL": "http://gitlab-sre-redpanda:8081",
    },
    "livekit": {
        "LIVEKIT_URL": "ws://gitlab-sre-livekit:7880",
        "LIVEKIT_HOST": "gitlab-sre-livekit",
        "LIVEKIT_PORT": "7880",
    },
    "localstack": {
        "AWS_ENDPOINT_URL": "http://gitlab-sre-localstack:4566",
        "LOCALSTACK_HOST": "gitlab-sre-localstack",
    },
}


class ComposeGenerator:
    """
    Generates docker-compose.yml files from project manifests.
    """
    
    def __init__(self, project_id: str, project_name: str):
        self.project_id = project_id
        self.project_name = project_name
    
    def _generate_service_block(
        self,
        service_config: ManifestServiceConfig,
        gitlab_path: str,
        dependencies: dict,
        db_name: str
    ) -> dict:
        """Generate a single service block for docker-compose"""
        
        service_name = f"{self.project_id}-{service_config.name}"
        container_name = f"gitlab-sre-{service_name}"
        
        # Base service configuration
        service = {
            "build": {
                "context": "." if service_config.type == ServiceType.BACKEND else f"./{service_config.name}",
                "dockerfile": "Dockerfile"
            },
            "container_name": container_name,
            "restart": "unless-stopped",
            "labels": [
                f"ravenhelm.gitlab.project={gitlab_path}",
                f"ravenhelm.service={service_config.name}",
                f"ravenhelm.workload={service_config.type.value}",
            ],
            "environment": {
                "NODE_ENV": "production" if service_config.type == ServiceType.FRONTEND else None,
                "LOG_LEVEL": "info",
            },
            "networks": ["platform_net"],
        }
        
        # Add port mapping
        internal_port = service_config.internal_port or service_config.port
        service["ports"] = [f"{service_config.port}:{internal_port}"]
        
        # Add health check if configured
        if service_config.health_check:
            service["healthcheck"] = {
                "test": ["CMD", "curl", "-f", f"http://localhost:{internal_port}{service_config.health_check}"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
                "start_period": "40s"
            }
        
        # Add shared service environment variables
        env = service["environment"]
        
        if dependencies.get("postgres"):
            for key, value in SHARED_SERVICE_ENV["postgres"].items():
                env[key] = value.format(db_name=db_name)
        
        if dependencies.get("redis"):
            env.update(SHARED_SERVICE_ENV["redis"])
        
        if dependencies.get("nats"):
            env.update(SHARED_SERVICE_ENV["nats"])
        
        if dependencies.get("redpanda"):
            env.update(SHARED_SERVICE_ENV["redpanda"])
        
        if dependencies.get("livekit"):
            env.update(SHARED_SERVICE_ENV["livekit"])
        
        if dependencies.get("localstack"):
            env.update(SHARED_SERVICE_ENV["localstack"])
        
        # Clean up None values
        service["environment"] = {k: v for k, v in env.items() if v is not None}
        
        # Add depends_on for backend services
        if service_config.type == ServiceType.BACKEND:
            depends_on = []
            if dependencies.get("postgres"):
                depends_on.append("gitlab-sre-postgres")
            if dependencies.get("redis"):
                depends_on.append("gitlab-sre-redis")
            if depends_on:
                service["depends_on"] = {
                    name: {"condition": "service_started"} 
                    for name in depends_on
                }
        
        return service
    
    def generate(
        self,
        manifest: ProjectManifest,
        gitlab_path: Optional[str] = None
    ) -> dict:
        """
        Generate a complete docker-compose.yml structure.
        
        Args:
            manifest: Parsed project manifest
            gitlab_path: GitLab project path (e.g., "ravenhelm/my-app")
            
        Returns:
            Dictionary representing docker-compose.yml content
        """
        gitlab_path = gitlab_path or manifest.project.get("gitlab_path", f"ravenhelm/{self.project_id}")
        db_name = self.project_id.replace("-", "_")
        
        # Get dependencies as dict
        deps = manifest.dependencies.model_dump() if hasattr(manifest.dependencies, 'model_dump') else manifest.dependencies.__dict__
        
        # Build services
        services = {}
        for svc_config in manifest.services:
            service_key = f"{self.project_id}-{svc_config.name}"
            services[service_key] = self._generate_service_block(
                svc_config,
                gitlab_path,
                deps,
                db_name
            )
        
        # Build networks section
        networks = {
            "platform_net": {
                "external": True
            }
        }
        
        # Add isolated network if configured
        if manifest.network.mode == "isolated":
            network_name = f"{self.project_id}_net"
            networks[network_name] = {
                "driver": "bridge"
            }
            if manifest.network.subnet:
                networks[network_name]["ipam"] = {
                    "config": [{"subnet": manifest.network.subnet}]
                }
            
            # Update services to use isolated network too
            for svc in services.values():
                svc["networks"].append(network_name)
        
        # Complete compose structure
        compose = {
            "version": "3.8",
            "services": services,
            "networks": networks
        }
        
        return compose
    
    def generate_yaml(
        self,
        manifest: ProjectManifest,
        gitlab_path: Optional[str] = None
    ) -> str:
        """
        Generate docker-compose.yml content as YAML string.
        
        Args:
            manifest: Parsed project manifest
            gitlab_path: GitLab project path
            
        Returns:
            YAML string ready to write to file
        """
        compose = self.generate(manifest, gitlab_path)
        
        # Custom YAML representer for cleaner output
        def str_representer(dumper, data):
            if '\n' in data:
                return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
            return dumper.represent_scalar('tag:yaml.org,2002:str', data)
        
        yaml.add_representer(str, str_representer)
        
        return yaml.dump(
            compose,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True
        )
    
    def save(
        self,
        manifest: ProjectManifest,
        output_path: Path,
        gitlab_path: Optional[str] = None
    ) -> Path:
        """
        Generate and save docker-compose.yml to file.
        
        Args:
            manifest: Parsed project manifest
            output_path: Directory to save the file
            gitlab_path: GitLab project path
            
        Returns:
            Path to the generated file
        """
        yaml_content = self.generate_yaml(manifest, gitlab_path)
        
        output_file = output_path / "docker-compose.yml"
        output_file.write_text(yaml_content)
        
        logger.info(
            "Generated docker-compose.yml",
            project_id=self.project_id,
            output=str(output_file)
        )
        
        return output_file


class ManifestGenerator:
    """
    Generates .hlidskjalf.yaml manifest files for new projects.
    """
    
    def __init__(self, project_id: str, project_name: str):
        self.project_id = project_id
        self.project_name = project_name
    
    def generate(
        self,
        gitlab_path: str,
        category: ProjectCategory,
        realm: Realm,
        api_port: int,
        ui_port: int,
        include_api: bool = True,
        include_ui: bool = True,
        include_worker: bool = False,
        use_postgres: bool = True,
        use_redis: bool = True,
        use_nats: bool = False,
        use_livekit: bool = False,
        isolated_network: bool = False
    ) -> ProjectManifest:
        """
        Generate a ProjectManifest for a new project.
        
        Args:
            gitlab_path: GitLab project path
            category: Project category
            realm: Target realm/environment
            api_port: Allocated API port
            ui_port: Allocated UI port
            include_api: Include API service
            include_ui: Include UI service
            include_worker: Include worker service
            use_*: Shared service dependencies
            isolated_network: Use isolated network instead of platform_net
            
        Returns:
            ProjectManifest instance
        """
        services = []
        
        if include_api:
            services.append(ManifestServiceConfig(
                name="api",
                type=ServiceType.BACKEND,
                port=api_port,
                internal_port=8000,
                health_check="/health",
                compose_service=f"{self.project_id}-api"
            ))
        
        if include_ui:
            services.append(ManifestServiceConfig(
                name="ui",
                type=ServiceType.FRONTEND,
                port=ui_port,
                internal_port=3000,
                health_check="/api/health",
                compose_service=f"{self.project_id}-ui"
            ))
        
        if include_worker:
            # Worker uses API port range, next port after API
            worker_port = api_port + 1 if include_api else api_port
            services.append(ManifestServiceConfig(
                name="worker",
                type=ServiceType.WORKER,
                port=worker_port,
                internal_port=8001,
                health_check="/health",
                compose_service=f"{self.project_id}-worker"
            ))
        
        from src.models.registry import ManifestDependencies, ManifestNetworkConfig
        
        manifest = ProjectManifest(
            version="1.0",
            project={
                "name": self.project_name,
                "gitlab_path": gitlab_path,
                "category": category.value,
                "realm": realm.value
            },
            services=services,
            dependencies=ManifestDependencies(
                postgres=use_postgres,
                redis=use_redis,
                nats=use_nats,
                livekit=use_livekit,
                localstack=True  # Always include LocalStack for secrets
            ),
            network=ManifestNetworkConfig(
                mode="isolated" if isolated_network else "shared"
            )
        )
        
        return manifest
    
    def generate_yaml(self, **kwargs) -> str:
        """Generate manifest as YAML string"""
        manifest = self.generate(**kwargs)
        
        # Convert to dict for YAML serialization
        manifest_dict = {
            "version": manifest.version,
            "project": manifest.project,
            "services": [
                {
                    "name": s.name,
                    "type": s.type.value,
                    "port": s.port,
                    "internal_port": s.internal_port,
                    "health_check": s.health_check,
                    "compose_service": s.compose_service
                }
                for s in manifest.services
            ],
            "dependencies": manifest.dependencies.model_dump() if hasattr(manifest.dependencies, 'model_dump') else manifest.dependencies.__dict__,
            "network": manifest.network.model_dump() if hasattr(manifest.network, 'model_dump') else manifest.network.__dict__
        }
        
        return yaml.dump(
            manifest_dict,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True
        )
    
    def save(self, output_path: Path, **kwargs) -> Path:
        """Generate and save manifest to file"""
        yaml_content = self.generate_yaml(**kwargs)
        
        output_file = output_path / ".hlidskjalf.yaml"
        output_file.write_text(yaml_content)
        
        logger.info(
            "Generated .hlidskjalf.yaml",
            project_id=self.project_id,
            output=str(output_file)
        )
        
        return output_file

