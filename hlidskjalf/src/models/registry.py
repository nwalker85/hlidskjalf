"""
Hliðskjálf - Registry Models
The records of all that exists across the Nine Realms.

Projects, Ports, Deployments, and the health of all services -
as observed by Huginn and remembered by Muninn.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """SQLAlchemy declarative base - The foundation of Yggdrasil"""
    pass


# =============================================================================
# The Nine Realms (Environments)
# =============================================================================

class Realm(str, Enum):
    """
    The Nine Realms of deployment.
    Each realm serves a purpose in the cosmic order.
    """
    MIDGARD = "midgard"          # Development - the mortal realm, where we build
    ALFHEIM = "alfheim"          # Staging - realm of light, pre-production
    ASGARD = "asgard"            # Production - realm of the gods, live and sacred
    NIFLHEIM = "niflheim"        # Disaster Recovery - the cold realm of mist
    MUSPELHEIM = "muspelheim"    # Load Testing - the fire realm, chaos engineering
    JOTUNHEIM = "jotunheim"      # Sandbox - realm of giants, experiments
    VANAHEIM = "vanaheim"        # Shared Services - realm of the Vanir, platform infra
    SVARTALFHEIM = "svartalfheim"  # Data - dark elf realm, databases and analytics
    HELHEIM = "helheim"          # Archive - realm of the dead, cold storage

# Alias for backward compatibility
Environment = Realm


class PortType(str, Enum):
    """Type of port allocation"""
    HTTP = "http"
    HTTPS = "https"
    GRPC = "grpc"
    METRICS = "metrics"
    DATABASE = "database"
    CUSTOM = "custom"


class ProjectCategory(str, Enum):
    """Project category - determines port range allocation"""
    PLATFORM = "platform"      # 8000-8099 (API), 3000-3099 (UI)
    PERSONAL = "personal"      # 8100-8199 (API), 3100-3199 (UI)
    WORK = "work"              # 8200-8299 (API), 3200-3299 (UI)
    SANDBOX = "sandbox"        # 8300-8399 (API), 3300-3399 (UI)


class ServiceType(str, Enum):
    """Type of service within a project"""
    BACKEND = "backend"
    FRONTEND = "frontend"
    WORKER = "worker"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    GATEWAY = "gateway"


class DeploymentStatus(str, Enum):
    """Deployment lifecycle status"""
    PENDING = "pending"
    DEPLOYING = "deploying"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    UNHEALTHY = "unhealthy"


class HealthStatus(str, Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# =============================================================================
# SQLAlchemy Models
# =============================================================================

class ProjectRecord(Base):
    """Project registry - tracks all registered projects in the platform"""
    __tablename__ = "projects"
    
    id = Column(String(50), primary_key=True)  # e.g., "saaa", "ravenmaskos"
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Git information
    git_repo_url = Column(String(500), nullable=True)
    git_branch = Column(String(100), default="main")
    
    # GitLab integration
    gitlab_id = Column(Integer, unique=True, nullable=True)
    gitlab_path = Column(String(200), nullable=True)  # e.g., "ravenhelm/my-new-app"
    gitlab_web_url = Column(String(500), nullable=True)
    gitlab_default_branch = Column(String(100), default="main")
    gitlab_last_activity = Column(DateTime(timezone=True), nullable=True)
    synced_at = Column(DateTime(timezone=True), nullable=True)
    
    # Nginx subdomain (e.g., "saaa" -> *.saaa.ravenhelm.test)
    subdomain = Column(String(50), nullable=False, unique=True)
    
    # Project categorization
    project_type = Column(String(50), default="application")  # application, service, infrastructure
    category = Column(SQLEnum(ProjectCategory), default=ProjectCategory.SANDBOX)
    realm = Column(SQLEnum(Realm), default=Realm.MIDGARD)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    ports = relationship("PortAllocation", back_populates="project", cascade="all, delete-orphan")
    deployments = relationship("Deployment", back_populates="project", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="project", cascade="all, delete-orphan")


class PortAllocation(Base):
    """Port registry - tracks all allocated ports across environments"""
    __tablename__ = "port_allocations"
    __table_args__ = (
        UniqueConstraint("port", "environment", name="uq_port_environment"),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), ForeignKey("projects.id"), nullable=False)
    
    # Port details
    port = Column(Integer, nullable=False)
    port_type = Column(SQLEnum(PortType), nullable=False)
    environment = Column(SQLEnum(Environment), nullable=False)
    
    # Service name (e.g., "frontend", "api", "worker")
    service_name = Column(String(100), nullable=False)
    
    # Internal port (container port)
    internal_port = Column(Integer, nullable=True)
    
    # Description
    description = Column(String(255), nullable=True)
    
    # Auto-assigned vs manually specified
    auto_assigned = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    project = relationship("ProjectRecord", back_populates="ports")


class Service(Base):
    """
    Service registry - tracks individual services within a project.
    A project can have multiple services (api, ui, worker, etc.)
    """
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_project_service"),
    )
    
    id = Column(String(100), primary_key=True)  # e.g., "my-new-app/api"
    project_id = Column(String(50), ForeignKey("projects.id"), nullable=False)
    
    # Service identity
    name = Column(String(100), nullable=False)  # e.g., "api", "ui", "worker"
    service_type = Column(SQLEnum(ServiceType), nullable=False)
    
    # Port configuration
    port = Column(Integer, nullable=False)  # External port (host-mapped)
    internal_port = Column(Integer, nullable=True)  # Container port
    
    # Health monitoring
    health_check_path = Column(String(200), nullable=True)  # e.g., "/health"
    health_check_interval = Column(Integer, default=30)  # seconds
    
    # Docker compose mapping
    compose_service = Column(String(100), nullable=True)  # docker-compose service name
    container_name = Column(String(100), nullable=True)  # expected container name
    
    # Domain configuration
    domain = Column(String(255), nullable=True)  # e.g., "my-app-api.ravenhelm.test"
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    project = relationship("ProjectRecord", back_populates="services")


class Deployment(Base):
    """Deployment registry - tracks all deployments across environments"""
    __tablename__ = "deployments"
    
    id = Column(String(100), primary_key=True)  # e.g., "saaa-dev-20240115"
    project_id = Column(String(50), ForeignKey("projects.id"), nullable=False)
    
    # Deployment info
    environment = Column(SQLEnum(Environment), nullable=False)
    status = Column(SQLEnum(DeploymentStatus), default=DeploymentStatus.PENDING)
    
    # Version tracking
    version = Column(String(50), nullable=True)
    git_commit = Column(String(40), nullable=True)
    
    # Docker/Infrastructure
    container_ids = Column(JSON, default=list)  # List of container IDs
    compose_file = Column(String(500), nullable=True)
    
    # Cloud deployment (for staging/prod)
    aws_account_id = Column(String(20), nullable=True)
    aws_region = Column(String(20), nullable=True)
    ecs_cluster = Column(String(100), nullable=True)
    ecs_service = Column(String(100), nullable=True)
    
    # Health & Metrics
    health_status = Column(SQLEnum(HealthStatus), default=HealthStatus.UNKNOWN)
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    health_check_url = Column(String(500), nullable=True)
    
    # Timestamps
    deployed_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    project = relationship("ProjectRecord", back_populates="deployments")
    health_checks = relationship("HealthCheckRecord", back_populates="deployment", cascade="all, delete-orphan")


class HealthCheckRecord(Base):
    """Health check history for deployments"""
    __tablename__ = "health_checks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    deployment_id = Column(String(100), ForeignKey("deployments.id"), nullable=False)
    
    # Check result
    status = Column(SQLEnum(HealthStatus), nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Metrics snapshot
    metrics_snapshot = Column(JSON, nullable=True)  # CPU, memory, etc.
    
    # Timestamp
    checked_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    deployment = relationship("Deployment", back_populates="health_checks")


class NginxRouteRecord(Base):
    """Nginx route configuration - generated from port registry"""
    __tablename__ = "nginx_routes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), ForeignKey("projects.id"), nullable=False)
    
    # Route configuration
    domain = Column(String(255), nullable=False)  # e.g., api.saaa.ravenhelm.test
    upstream_host = Column(String(255), nullable=False)  # e.g., host.docker.internal
    upstream_port = Column(Integer, nullable=False)
    
    # SSL
    ssl_enabled = Column(Boolean, default=True)
    
    # Proxy settings
    proxy_timeout = Column(Integer, default=60)
    proxy_buffer_size = Column(String(10), default="128k")
    
    # Additional headers
    custom_headers = Column(JSON, default=dict)
    
    # Active/Inactive
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# =============================================================================
# Pydantic Schemas (API Models)
# =============================================================================

class ProjectCreate(BaseModel):
    """Create a new project"""
    id: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z][a-z0-9-]*$")
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    git_repo_url: Optional[str] = None
    subdomain: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z][a-z0-9-]*$")
    project_type: str = "application"
    category: ProjectCategory = ProjectCategory.SANDBOX
    realm: Realm = Realm.MIDGARD


class ProjectScaffoldRequest(BaseModel):
    """Request to scaffold a new project with GitLab integration"""
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    category: ProjectCategory = ProjectCategory.WORK
    realm: Realm = Realm.ALFHEIM
    template: str = "ravenmaskos"  # or "platform-template"
    group: str = "ravenhelm"
    
    # Service configuration
    include_api: bool = True
    include_ui: bool = True
    include_worker: bool = False
    
    # Shared service dependencies
    use_postgres: bool = True
    use_redis: bool = True
    use_nats: bool = False
    use_livekit: bool = False
    
    # Network mode
    isolated_network: bool = False  # If true, creates project-specific network


class ProjectResponse(BaseModel):
    """Project response model"""
    id: str
    name: str
    description: Optional[str]
    git_repo_url: Optional[str]
    subdomain: str
    project_type: str
    category: Optional[ProjectCategory]
    realm: Optional[Realm]
    gitlab_id: Optional[int]
    gitlab_path: Optional[str]
    gitlab_web_url: Optional[str]
    synced_at: Optional[datetime]
    created_at: datetime
    ports: list["PortAllocationResponse"]
    services: list["ServiceResponse"] = []
    
    class Config:
        from_attributes = True


class PortRequest(BaseModel):
    """Request a port allocation"""
    project_id: str
    service_name: str
    port_type: PortType = PortType.HTTP
    environment: Environment = Environment.MIDGARD
    preferred_port: Optional[int] = None
    internal_port: Optional[int] = None
    description: Optional[str] = None


class PortAllocationResponse(BaseModel):
    """Port allocation response"""
    id: int
    project_id: str
    service_name: str
    port: int
    port_type: PortType
    environment: Environment
    internal_port: Optional[int]
    auto_assigned: bool
    description: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ServiceCreate(BaseModel):
    """Create a new service within a project"""
    name: str = Field(..., min_length=1, max_length=100)
    service_type: ServiceType
    port: int = Field(..., ge=1024, le=65535)
    internal_port: Optional[int] = Field(None, ge=1, le=65535)
    health_check_path: Optional[str] = None
    compose_service: Optional[str] = None
    domain: Optional[str] = None


class ServiceResponse(BaseModel):
    """Service response model"""
    id: str
    project_id: str
    name: str
    service_type: ServiceType
    port: int
    internal_port: Optional[int]
    health_check_path: Optional[str]
    compose_service: Optional[str]
    container_name: Optional[str]
    domain: Optional[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class DeploymentCreate(BaseModel):
    """Create/register a deployment"""
    project_id: str
    environment: Environment
    version: Optional[str] = None
    git_commit: Optional[str] = None
    compose_file: Optional[str] = None
    health_check_url: Optional[str] = None


class DeploymentResponse(BaseModel):
    """Deployment response model"""
    id: str
    project_id: str
    environment: Environment
    status: DeploymentStatus
    health_status: HealthStatus
    version: Optional[str]
    git_commit: Optional[str]
    deployed_at: datetime
    last_health_check: Optional[datetime]
    
    class Config:
        from_attributes = True


class HealthCheckResponse(BaseModel):
    """Health check response"""
    deployment_id: str
    status: HealthStatus
    response_time_ms: Optional[int]
    metrics_snapshot: Optional[dict]
    checked_at: datetime
    
    class Config:
        from_attributes = True


class PlatformOverview(BaseModel):
    """Platform-wide overview for dashboard"""
    total_projects: int
    total_deployments: int
    healthy_deployments: int
    unhealthy_deployments: int
    ports_allocated: int
    ports_available: int
    environments: dict[str, int]  # Count by environment
    recent_health_checks: list[HealthCheckResponse]


# =============================================================================
# Manifest Schema Models
# =============================================================================

class ManifestServiceConfig(BaseModel):
    """Service configuration within .hlidskjalf.yaml manifest"""
    name: str
    type: ServiceType
    port: int
    internal_port: Optional[int] = None
    health_check: Optional[str] = None
    compose_service: Optional[str] = None


class ManifestDependencies(BaseModel):
    """Shared service dependencies"""
    postgres: bool = False
    redis: bool = False
    nats: bool = False
    redpanda: bool = False
    livekit: bool = False
    localstack: bool = False


class ManifestNetworkConfig(BaseModel):
    """Network configuration"""
    mode: str = "shared"  # "shared" (platform_net) or "isolated"
    subnet: Optional[str] = None  # For isolated mode


class ProjectManifest(BaseModel):
    """
    Schema for .hlidskjalf.yaml manifest file.
    This lives in each GitLab repo and defines the project's services.
    """
    version: str = "1.0"
    
    # Project metadata
    project: dict = Field(default_factory=lambda: {
        "name": "",
        "gitlab_path": "",
        "category": "sandbox",
        "realm": "midgard"
    })
    
    # Services
    services: list[ManifestServiceConfig] = Field(default_factory=list)
    
    # Dependencies on shared services
    dependencies: ManifestDependencies = Field(default_factory=ManifestDependencies)
    
    # Network configuration
    network: ManifestNetworkConfig = Field(default_factory=ManifestNetworkConfig)
    
    class Config:
        extra = "allow"  # Allow additional fields for extensibility

