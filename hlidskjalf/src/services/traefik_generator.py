"""
Traefik Configuration Generator
Generates router and service entries for ravenhelm-proxy/dynamic.yml

Produces properly configured Traefik routing for new projects:
- Routers with correct middleware chains
- Service backends pointing to correct ports
- TLS configuration
"""

from pathlib import Path
from typing import Optional, List
import yaml

import structlog

from src.models.registry import (
    ProjectManifest,
    ManifestServiceConfig,
    ServiceType,
    Realm,
)

logger = structlog.get_logger(__name__)


# Domain suffixes by realm
REALM_DOMAINS = {
    Realm.MIDGARD: ".ravenhelm.test",      # Development
    Realm.ALFHEIM: ".ravenhelm.dev",        # Staging
    Realm.ASGARD: ".ravenhelm.ai",          # Production
}

# Default middleware chains by service type
DEFAULT_MIDDLEWARES = {
    ServiceType.FRONTEND: ["secure-headers"],
    ServiceType.BACKEND: ["cors-all", "secure-headers"],
    ServiceType.WORKER: ["protected"],
    ServiceType.GATEWAY: ["cors-all", "secure-headers"],
}


class TraefikRouteConfig:
    """Configuration for a single Traefik route"""
    
    def __init__(
        self,
        name: str,
        hosts: List[str],
        service_name: str,
        port: int,
        middlewares: List[str] = None,
        path_prefix: Optional[str] = None,
        priority: int = 100,
        use_internal_dns: bool = False,
        container_name: Optional[str] = None
    ):
        self.name = name
        self.hosts = hosts
        self.service_name = service_name
        self.port = port
        self.middlewares = middlewares or ["secure-headers"]
        self.path_prefix = path_prefix
        self.priority = priority
        self.use_internal_dns = use_internal_dns
        self.container_name = container_name
    
    def to_router_config(self) -> dict:
        """Generate router configuration"""
        # Build host rule
        host_rules = [f'Host(`{host}`)' for host in self.hosts]
        rule = " || ".join(host_rules)
        
        # Add path prefix if specified
        if self.path_prefix:
            rule = f"({rule}) && PathPrefix(`{self.path_prefix}`)"
        
        config = {
            "rule": rule,
            "service": f"{self.service_name}-svc",
            "middlewares": self.middlewares,
            "tls": {}
        }
        
        if self.priority != 100:
            config["priority"] = self.priority
        
        return config
    
    def to_service_config(self) -> dict:
        """Generate service (backend) configuration"""
        if self.use_internal_dns and self.container_name:
            # Use Docker internal DNS
            url = f"http://{self.container_name}:{self.port}"
        else:
            # Use host.docker.internal
            url = f"http://host.docker.internal:{self.port}"
        
        return {
            "loadBalancer": {
                "servers": [{"url": url}]
            }
        }


class TraefikGenerator:
    """
    Generates Traefik dynamic configuration for projects.
    """
    
    def __init__(self, project_id: str, project_name: str):
        self.project_id = project_id
        self.project_name = project_name
    
    def _get_domain(self, realm: Realm) -> str:
        """Get domain suffix for realm"""
        return REALM_DOMAINS.get(realm, ".ravenhelm.test")
    
    def _get_middlewares(
        self,
        service_type: ServiceType,
        protected: bool = False
    ) -> List[str]:
        """Get appropriate middleware chain"""
        if protected:
            return ["protected"]
        return DEFAULT_MIDDLEWARES.get(service_type, ["secure-headers"])
    
    def generate_routes(
        self,
        manifest: ProjectManifest,
        realm: Realm = Realm.MIDGARD
    ) -> List[TraefikRouteConfig]:
        """
        Generate Traefik route configurations from manifest.
        
        Args:
            manifest: Parsed project manifest
            realm: Target realm/environment
            
        Returns:
            List of TraefikRouteConfig objects
        """
        routes = []
        domain_suffix = self._get_domain(realm)
        
        for svc in manifest.services:
            # Primary domain based on service type
            if svc.type == ServiceType.FRONTEND:
                # Frontend gets the base domain
                hosts = [f"{self.project_id}{domain_suffix}"]
            else:
                # API/backend get subdomain
                hosts = [f"{self.project_id}-{svc.name}{domain_suffix}"]
            
            # Build route name
            route_name = f"{self.project_id}-{svc.name}"
            
            routes.append(TraefikRouteConfig(
                name=route_name,
                hosts=hosts,
                service_name=route_name,
                port=svc.port,
                middlewares=self._get_middlewares(svc.type),
                container_name=svc.compose_service or f"gitlab-sre-{route_name}"
            ))
        
        return routes
    
    def generate_yaml_snippet(
        self,
        manifest: ProjectManifest,
        realm: Realm = Realm.MIDGARD
    ) -> dict:
        """
        Generate YAML snippet to add to dynamic.yml.
        
        Args:
            manifest: Parsed project manifest
            realm: Target realm/environment
            
        Returns:
            Dictionary with routers and services sections
        """
        routes = self.generate_routes(manifest, realm)
        
        routers = {}
        services = {}
        
        for route in routes:
            routers[route.name] = route.to_router_config()
            services[f"{route.service_name}-svc"] = route.to_service_config()
        
        return {
            "routers": routers,
            "services": services
        }
    
    def to_yaml(
        self,
        manifest: ProjectManifest,
        realm: Realm = Realm.MIDGARD
    ) -> str:
        """
        Generate YAML string to append to dynamic.yml.
        
        Args:
            manifest: Parsed project manifest
            realm: Target realm/environment
            
        Returns:
            YAML string with router and service definitions
        """
        snippet = self.generate_yaml_snippet(manifest, realm)
        
        # Build formatted output
        lines = [
            f"    # ─────────────────────────────────────────────────────────────────────────",
            f"    # {self.project_name.upper()} - Auto-generated routes",
            f"    # ─────────────────────────────────────────────────────────────────────────",
            ""
        ]
        
        # Add routers
        for name, config in snippet["routers"].items():
            lines.append(f"    {name}:")
            lines.append(f'      rule: "{config["rule"]}"')
            lines.append(f"      service: {config['service']}")
            lines.append(f"      middlewares:")
            for mw in config["middlewares"]:
                lines.append(f"        - {mw}")
            lines.append("      tls: {}")
            lines.append("")
        
        return "\n".join(lines)
    
    def to_services_yaml(
        self,
        manifest: ProjectManifest,
        realm: Realm = Realm.MIDGARD
    ) -> str:
        """
        Generate YAML string for services section.
        
        Args:
            manifest: Parsed project manifest
            realm: Target realm/environment
            
        Returns:
            YAML string with service definitions
        """
        snippet = self.generate_yaml_snippet(manifest, realm)
        
        lines = [
            f"    # {self.project_name} services",
        ]
        
        for name, config in snippet["services"].items():
            lines.append(f"    {name}:")
            lines.append(f"      loadBalancer:")
            lines.append(f"        servers:")
            for server in config["loadBalancer"]["servers"]:
                lines.append(f'          - url: "{server["url"]}"')
        
        return "\n".join(lines)
    
    def update_dynamic_yml(
        self,
        manifest: ProjectManifest,
        dynamic_yml_path: Path,
        realm: Realm = Realm.MIDGARD
    ) -> None:
        """
        Update dynamic.yml file with new project routes.
        
        This appends the new router and service entries to the appropriate
        sections in the dynamic.yml file.
        
        Args:
            manifest: Parsed project manifest
            dynamic_yml_path: Path to dynamic.yml
            realm: Target realm/environment
        """
        # Load existing config
        with open(dynamic_yml_path) as f:
            content = f.read()
            config = yaml.safe_load(content)
        
        # Generate new entries
        snippet = self.generate_yaml_snippet(manifest, realm)
        
        # Add to existing config
        if "http" not in config:
            config["http"] = {}
        
        if "routers" not in config["http"]:
            config["http"]["routers"] = {}
        
        if "services" not in config["http"]:
            config["http"]["services"] = {}
        
        # Merge new routers and services
        config["http"]["routers"].update(snippet["routers"])
        config["http"]["services"].update(snippet["services"])
        
        # Write back
        with open(dynamic_yml_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        logger.info(
            "Updated Traefik dynamic.yml",
            project_id=self.project_id,
            routers=list(snippet["routers"].keys()),
            services=list(snippet["services"].keys())
        )
    
    def generate_cors_origin(self, realm: Realm = Realm.MIDGARD) -> str:
        """
        Generate CORS origin URL for this project.
        
        Returns:
            Full HTTPS URL for CORS allow list
        """
        domain_suffix = self._get_domain(realm)
        return f"https://{self.project_id}{domain_suffix}"


def add_cors_origin_to_middleware(
    dynamic_yml_path: Path,
    origin: str,
    middleware_name: str = "cors-ravenhelm"
) -> None:
    """
    Add a new CORS origin to an existing middleware.
    
    Args:
        dynamic_yml_path: Path to dynamic.yml
        origin: CORS origin URL to add
        middleware_name: Name of middleware to update
    """
    with open(dynamic_yml_path) as f:
        config = yaml.safe_load(f)
    
    middlewares = config.get("http", {}).get("middlewares", {})
    middleware = middlewares.get(middleware_name, {})
    
    headers = middleware.get("headers", {})
    origins = headers.get("accessControlAllowOriginList", [])
    
    if origin not in origins:
        origins.append(origin)
        headers["accessControlAllowOriginList"] = origins
        middleware["headers"] = headers
        middlewares[middleware_name] = middleware
        
        if "http" not in config:
            config["http"] = {}
        config["http"]["middlewares"] = middlewares
        
        with open(dynamic_yml_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        logger.info(
            "Added CORS origin to middleware",
            origin=origin,
            middleware=middleware_name
        )

