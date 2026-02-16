"""
Deployment Manager Service
Tracks and manages deployments across dev, staging, and production environments
"""

import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Optional
import docker
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.core.config import get_settings
from src.models.registry import (
    ProjectRecord,
    Deployment,
    HealthCheckRecord,
    DeploymentStatus,
    HealthStatus,
    Environment,
    DeploymentCreate,
    DeploymentResponse,
    HealthCheckResponse,
)

logger = get_logger(__name__)
settings = get_settings()


class DeploymentManager:
    """
    Manages deployment lifecycle and health monitoring
    
    Integrates with:
    - Docker for local development deployments
    - AWS ECS/EKS for cloud deployments (staging/production)
    - Prometheus for metrics collection
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._docker_client: Optional[docker.DockerClient] = None
    
    @property
    def docker_client(self) -> docker.DockerClient:
        """Lazy-load Docker client"""
        if self._docker_client is None:
            self._docker_client = docker.from_env()
        return self._docker_client
    
    async def register_deployment(
        self,
        deployment: DeploymentCreate
    ) -> DeploymentResponse:
        """Register a new deployment"""
        # Generate deployment ID
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        deployment_id = f"{deployment.project_id}-{deployment.environment.value}-{timestamp}"
        
        # Check project exists
        result = await self.session.execute(
            select(ProjectRecord).where(ProjectRecord.id == deployment.project_id)
        )
        project = result.scalar_one_or_none()
        
        if not project:
            raise ValueError(f"Project {deployment.project_id} not found")
        
        # Create deployment record
        record = Deployment(
            id=deployment_id,
            project_id=deployment.project_id,
            environment=deployment.environment,
            status=DeploymentStatus.PENDING,
            version=deployment.version,
            git_commit=deployment.git_commit,
            compose_file=deployment.compose_file,
            health_check_url=deployment.health_check_url,
        )
        
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        
        logger.info(
            "Deployment registered",
            deployment_id=deployment_id,
            project_id=deployment.project_id,
            environment=deployment.environment.value
        )
        
        return DeploymentResponse.model_validate(record)
    
    async def update_status(
        self,
        deployment_id: str,
        status: DeploymentStatus,
        container_ids: Optional[list[str]] = None
    ) -> DeploymentResponse:
        """Update deployment status"""
        result = await self.session.execute(
            select(Deployment).where(Deployment.id == deployment_id)
        )
        deployment = result.scalar_one_or_none()
        
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")
        
        deployment.status = status
        if container_ids:
            deployment.container_ids = container_ids
        
        await self.session.commit()
        await self.session.refresh(deployment)
        
        return DeploymentResponse.model_validate(deployment)
    
    async def get_deployments(
        self,
        project_id: Optional[str] = None,
        environment: Optional[Environment] = None,
        status: Optional[DeploymentStatus] = None,
    ) -> list[DeploymentResponse]:
        """Get deployments with optional filters"""
        query = select(Deployment)
        
        conditions = []
        if project_id:
            conditions.append(Deployment.project_id == project_id)
        if environment:
            conditions.append(Deployment.environment == environment)
        if status:
            conditions.append(Deployment.status == status)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(Deployment.deployed_at.desc())
        
        result = await self.session.execute(query)
        deployments = result.scalars().all()
        
        return [DeploymentResponse.model_validate(d) for d in deployments]
    
    async def check_health(self, deployment_id: str) -> HealthCheckResponse:
        """
        Perform health check on a deployment
        
        For local (dev) deployments: HTTP check or Docker inspect
        For cloud deployments: AWS ECS/EKS health status
        """
        result = await self.session.execute(
            select(Deployment).where(Deployment.id == deployment_id)
        )
        deployment = result.scalar_one_or_none()
        
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")
        
        health_status = HealthStatus.UNKNOWN
        response_time_ms = None
        error_message = None
        metrics_snapshot = {}
        
        try:
            if deployment.environment == Environment.MIDGARD:
                # Local health check
                health_status, response_time_ms, metrics_snapshot = await self._check_local_health(
                    deployment
                )
            else:
                # Cloud health check (AWS)
                health_status, metrics_snapshot = await self._check_cloud_health(deployment)
        
        except Exception as e:
            health_status = HealthStatus.UNHEALTHY
            error_message = str(e)
            logger.error(
                "Health check failed",
                deployment_id=deployment_id,
                error=str(e)
            )
        
        # Record health check
        health_record = HealthCheckRecord(
            deployment_id=deployment_id,
            status=health_status,
            response_time_ms=response_time_ms,
            error_message=error_message,
            metrics_snapshot=metrics_snapshot,
        )
        
        self.session.add(health_record)
        
        # Update deployment health status
        deployment.health_status = health_status
        deployment.last_health_check = datetime.utcnow()
        
        # Update deployment status based on health
        if health_status == HealthStatus.UNHEALTHY:
            deployment.status = DeploymentStatus.UNHEALTHY
        elif health_status == HealthStatus.HEALTHY and deployment.status == DeploymentStatus.UNHEALTHY:
            deployment.status = DeploymentStatus.RUNNING
        
        await self.session.commit()
        await self.session.refresh(health_record)
        
        return HealthCheckResponse.model_validate(health_record)
    
    async def _check_local_health(
        self,
        deployment: Deployment
    ) -> tuple[HealthStatus, Optional[int], dict]:
        """Check health of local Docker deployment"""
        metrics = {}
        
        # Try HTTP health check first
        if deployment.health_check_url:
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                start = datetime.utcnow()
                response = await client.get(deployment.health_check_url)
                response_time = int((datetime.utcnow() - start).total_seconds() * 1000)
                
                if response.status_code == 200:
                    return HealthStatus.HEALTHY, response_time, {"status_code": 200}
                elif response.status_code < 500:
                    return HealthStatus.DEGRADED, response_time, {"status_code": response.status_code}
                else:
                    return HealthStatus.UNHEALTHY, response_time, {"status_code": response.status_code}
        
        # Fall back to Docker container health
        if deployment.container_ids:
            healthy_count = 0
            total_count = len(deployment.container_ids)
            
            for container_id in deployment.container_ids:
                try:
                    container = self.docker_client.containers.get(container_id)
                    status = container.status
                    
                    if status == "running":
                        healthy_count += 1
                        
                        # Get container stats
                        stats = container.stats(stream=False)
                        metrics[container_id] = {
                            "status": status,
                            "cpu_percent": self._calculate_cpu_percent(stats),
                            "memory_mb": stats.get("memory_stats", {}).get("usage", 0) / 1024 / 1024,
                        }
                except docker.errors.NotFound:
                    logger.warning(f"Container {container_id} not found")
            
            if healthy_count == total_count:
                return HealthStatus.HEALTHY, None, metrics
            elif healthy_count > 0:
                return HealthStatus.DEGRADED, None, metrics
            else:
                return HealthStatus.UNHEALTHY, None, metrics
        
        return HealthStatus.UNKNOWN, None, metrics
    
    async def _check_cloud_health(
        self,
        deployment: Deployment
    ) -> tuple[HealthStatus, dict]:
        """Check health of AWS ECS deployment"""
        # TODO: Implement AWS ECS health check
        # This would use boto3 to check ECS service status
        return HealthStatus.UNKNOWN, {}
    
    def _calculate_cpu_percent(self, stats: dict) -> float:
        """Calculate CPU percentage from Docker stats"""
        try:
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]
            
            if system_delta > 0:
                cpu_count = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [1]))
                return (cpu_delta / system_delta) * cpu_count * 100.0
        except (KeyError, ZeroDivisionError):
            pass
        
        return 0.0
    
    async def discover_docker_deployments(self) -> list[dict]:
        """
        Discover running Docker deployments by scanning for ravenhelm labels
        
        Expected labels:
        - ravenhelm.project: project ID
        - ravenhelm.service: service name
        - ravenhelm.workload: workload name (for SPIRE)
        """
        discovered = []
        
        try:
            containers = self.docker_client.containers.list(
                filters={"label": "ravenhelm.project"}
            )
            
            for container in containers:
                labels = container.labels
                discovered.append({
                    "container_id": container.id[:12],
                    "container_name": container.name,
                    "project_id": labels.get("ravenhelm.project"),
                    "service_name": labels.get("ravenhelm.service", "unknown"),
                    "status": container.status,
                    "ports": container.ports,
                    "created": container.attrs.get("Created"),
                })
        
        except Exception as e:
            logger.error("Failed to discover Docker deployments", error=str(e))
        
        return discovered


class DockerDiscoveryJob:
    """
    Background job to discover and sync Docker containers to deployment records
    """
    
    def __init__(self, session_factory, interval_seconds: int = 30):
        self.session_factory = session_factory
        self.interval_seconds = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the Docker discovery job"""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Docker discovery job started", interval=self.interval_seconds)
    
    async def stop(self):
        """Stop the Docker discovery job"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Docker discovery job stopped")
    
    async def _run_loop(self):
        """Main discovery loop"""
        while self._running:
            try:
                async with self.session_factory() as session:
                    manager = DeploymentManager(session)
                    discovered = await manager.discover_docker_deployments()
                    
                    # Update or create deployment records for discovered containers
                    for container_info in discovered:
                        project_id = container_info.get("project_id")
                        if not project_id:
                            continue
                        
                        # Check if project exists
                        project_result = await session.execute(
                            select(ProjectRecord).where(ProjectRecord.id == project_id)
                        )
                        project = project_result.scalar_one_or_none()
                        if not project:
                            # Skip containers for unknown projects
                            continue
                        
                        # Find existing deployment for this project in dev environment
                        result = await session.execute(
                            select(Deployment).where(
                                and_(
                                    Deployment.project_id == project_id,
                                    Deployment.environment == Environment.MIDGARD
                                )
                            ).order_by(Deployment.deployed_at.desc()).limit(1)
                        )
                        deployment = result.scalar_one_or_none()
                        
                        container_id = container_info["container_id"]
                        
                        if deployment:
                            # Update existing deployment
                            container_ids = deployment.container_ids or []
                            if container_id not in container_ids:
                                container_ids.append(container_id)
                                deployment.container_ids = container_ids
                        else:
                            # Create new deployment for this project
                            # Generate ID: project-environment-timestamp
                            from datetime import datetime
                            deployment_id = f"{project_id}-midgard-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                            deployment = Deployment(
                                id=deployment_id,
                                project_id=project_id,
                                environment=Environment.MIDGARD,
                                version="docker-discovered",
                                container_ids=[container_id],
                                status=DeploymentStatus.RUNNING if container_info["status"] == "running" else DeploymentStatus.STOPPED,
                                health_status=HealthStatus.UNKNOWN,
                            )
                            session.add(deployment)
                            logger.info(
                                "Created deployment from Docker discovery",
                                project_id=project_id,
                                deployment_id=deployment_id,
                                container_id=container_id
                            )
                        
                        # Update status based on container status
                        if container_info["status"] == "running":
                            deployment.status = DeploymentStatus.RUNNING
                        elif container_info["status"] in ["exited", "dead"]:
                            deployment.status = DeploymentStatus.STOPPED
                    
                    await session.commit()
                    
                    if discovered:
                        logger.debug(
                            "Docker discovery complete",
                            containers_found=len(discovered)
                        )
                
            except Exception as e:
                logger.error("Docker discovery error", error=str(e), exc_info=True)
            
            # Wait before next discovery
            await asyncio.sleep(self.interval_seconds)


class HealthCheckScheduler:
    """
    Background scheduler for periodic health checks
    """
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the health check scheduler"""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Health check scheduler started")
    
    async def stop(self):
        """Stop the health check scheduler"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health check scheduler stopped")
    
    async def _run_loop(self):
        """Main scheduling loop"""
        while self._running:
            try:
                async with self.session_factory() as session:
                    manager = DeploymentManager(session)
                    
                    # Get all running deployments
                    deployments = await manager.get_deployments(
                        status=DeploymentStatus.RUNNING
                    )
                    
                    # Check health of each
                    for deployment in deployments:
                        try:
                            await manager.check_health(deployment.id)
                        except Exception as e:
                            logger.error(
                                "Health check failed",
                                deployment_id=deployment.id,
                                error=str(e)
                            )
                
                # Wait for next interval
                await asyncio.sleep(settings.HEALTH_CHECK_INTERVAL_SECONDS)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Health check loop error", error=str(e))
                await asyncio.sleep(5)  # Brief pause before retry

