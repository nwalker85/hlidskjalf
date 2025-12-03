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
    
    # Nginx subdomain (e.g., "saaa" -> *.saaa.ravenhelm.test)
    subdomain = Column(String(50), nullable=False, unique=True)
    
    # Project type
    project_type = Column(String(50), default="application")  # application, service, infrastructure
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    ports = relationship("PortAllocation", back_populates="project", cascade="all, delete-orphan")
    deployments = relationship("Deployment", back_populates="project", cascade="all, delete-orphan")


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


class ProjectResponse(BaseModel):
    """Project response model"""
    id: str
    name: str
    description: Optional[str]
    git_repo_url: Optional[str]
    subdomain: str
    project_type: str
    created_at: datetime
    ports: list["PortAllocationResponse"]
    
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

