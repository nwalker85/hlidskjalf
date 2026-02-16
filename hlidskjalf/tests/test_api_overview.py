"""
Tests for platform overview and health summary API endpoints
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.registry import (
    ProjectRecord,
    Deployment,
    HealthCheckRecord,
    Environment,
    DeploymentStatus,
    HealthStatus,
)


@pytest.mark.asyncio
async def test_get_platform_overview(client: AsyncClient, db_session: AsyncSession):
    """Test GET /api/v1/overview endpoint"""
    
    # Create test data
    project = ProjectRecord(
        id="test-project",
        name="Test Project",
        subdomain="test",
        project_type="application"
    )
    db_session.add(project)
    
    deployment = Deployment(
        id="test-project-midgard-001",
        project_id="test-project",
        environment=Environment.MIDGARD,
        status=DeploymentStatus.RUNNING,
        health_status=HealthStatus.HEALTHY
    )
    db_session.add(deployment)
    
    await db_session.commit()
    
    # Test the endpoint
    response = await client.get("/api/v1/overview")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total_projects"] >= 1
    assert data["total_deployments"] >= 1
    assert data["healthy_deployments"] >= 1
    assert "ports_allocated" in data
    assert "environments" in data
    assert isinstance(data["recent_health_checks"], list)


@pytest.mark.asyncio
async def test_get_health_summary(client: AsyncClient, db_session: AsyncSession):
    """Test GET /api/v1/health/summary endpoint"""
    
    # Create test data
    project = ProjectRecord(
        id="health-test",
        name="Health Test",
        subdomain="health-test",
        project_type="application"
    )
    db_session.add(project)
    
    # Create healthy deployment
    healthy_deployment = Deployment(
        id="health-test-midgard-001",
        project_id="health-test",
        environment=Environment.MIDGARD,
        status=DeploymentStatus.RUNNING,
        health_status=HealthStatus.HEALTHY
    )
    db_session.add(healthy_deployment)
    
    # Create unhealthy deployment
    unhealthy_deployment = Deployment(
        id="health-test-alfheim-001",
        project_id="health-test",
        environment=Environment.ALFHEIM,
        status=DeploymentStatus.RUNNING,
        health_status=HealthStatus.UNHEALTHY
    )
    db_session.add(unhealthy_deployment)
    
    await db_session.commit()
    
    # Test the endpoint
    response = await client.get("/api/v1/health/summary")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "health_counts" in data
    assert "realm_health" in data
    assert "uptime_percentage" in data
    assert "recent_failures" in data
    
    # Verify counts
    assert data["health_counts"]["healthy"] >= 1
    assert data["health_counts"]["unhealthy"] >= 1


@pytest.mark.asyncio
async def test_get_project_health(client: AsyncClient, db_session: AsyncSession):
    """Test GET /api/v1/projects/{project_id}/health endpoint"""
    
    # Create test data
    project = ProjectRecord(
        id="project-health-test",
        name="Project Health Test",
        subdomain="project-health",
        project_type="application"
    )
    db_session.add(project)
    
    deployment = Deployment(
        id="project-health-test-midgard-001",
        project_id="project-health-test",
        environment=Environment.MIDGARD,
        status=DeploymentStatus.RUNNING,
        health_status=HealthStatus.HEALTHY
    )
    db_session.add(deployment)
    
    # Add health check records
    health_check = HealthCheckRecord(
        deployment_id="project-health-test-midgard-001",
        status=HealthStatus.HEALTHY,
        response_time_ms=150
    )
    db_session.add(health_check)
    
    await db_session.commit()
    
    # Test the endpoint
    response = await client.get("/api/v1/projects/project-health-test/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["project_id"] == "project-health-test"
    assert data["project_name"] == "Project Health Test"
    assert len(data["deployments"]) >= 1
    assert data["overall_health"] in ["healthy", "degraded", "unhealthy", "unknown"]
    
    # Verify deployment details
    deployment_data = data["deployments"][0]
    assert deployment_data["environment"] == "midgard"
    assert deployment_data["health_status"] == "healthy"
    assert len(deployment_data["recent_checks"]) >= 1


@pytest.mark.asyncio
async def test_get_project_health_not_found(client: AsyncClient):
    """Test GET /api/v1/projects/{project_id}/health with non-existent project"""
    
    response = await client.get("/api/v1/projects/non-existent-project/health")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_projects_with_realm_filter(client: AsyncClient, db_session: AsyncSession):
    """Test GET /api/v1/projects?realm={realm} endpoint"""
    
    # Create projects in different realms
    project1 = ProjectRecord(
        id="midgard-project",
        name="Midgard Project",
        subdomain="midgard-proj",
        project_type="application"
    )
    db_session.add(project1)
    
    deployment1 = Deployment(
        id="midgard-project-midgard-001",
        project_id="midgard-project",
        environment=Environment.MIDGARD,
        status=DeploymentStatus.RUNNING,
        health_status=HealthStatus.HEALTHY
    )
    db_session.add(deployment1)
    
    project2 = ProjectRecord(
        id="alfheim-project",
        name="Alfheim Project",
        subdomain="alfheim-proj",
        project_type="application"
    )
    db_session.add(project2)
    
    deployment2 = Deployment(
        id="alfheim-project-alfheim-001",
        project_id="alfheim-project",
        environment=Environment.ALFHEIM,
        status=DeploymentStatus.RUNNING,
        health_status=HealthStatus.HEALTHY
    )
    db_session.add(deployment2)
    
    await db_session.commit()
    
    # Test without filter
    response = await client.get("/api/v1/projects")
    assert response.status_code == 200
    all_projects = response.json()
    assert len(all_projects) >= 2
    
    # Test with midgard filter
    response = await client.get("/api/v1/projects?realm=midgard")
    assert response.status_code == 200
    midgard_projects = response.json()
    assert any(p["id"] == "midgard-project" for p in midgard_projects)
    
    # Test with alfheim filter
    response = await client.get("/api/v1/projects?realm=alfheim")
    assert response.status_code == 200
    alfheim_projects = response.json()
    assert any(p["id"] == "alfheim-project" for p in alfheim_projects)

