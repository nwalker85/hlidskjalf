"""Tests for authorization API routes."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_check_permission_unauthorized(client: AsyncClient) -> None:
    """Test permission check without authentication returns 401."""
    response = await client.post(
        "/authz/check",
        json={
            "user_id": "test-user",
            "relation": "admin",
            "object_type": "organization",
            "object_id": "test-org",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_objects_unauthorized(client: AsyncClient) -> None:
    """Test list objects without authentication returns 401."""
    response = await client.post(
        "/authz/objects",
        json={
            "user_id": "test-user",
            "relation": "member",
            "object_type": "organization",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_write_tuple_unauthorized(client: AsyncClient) -> None:
    """Test write tuple without authentication returns 401."""
    response = await client.post(
        "/authz/tuples",
        json={
            "user_id": "test-user",
            "relation": "member",
            "object_type": "organization",
            "object_id": "test-org",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_tuple_unauthorized(client: AsyncClient) -> None:
    """Test delete tuple without authentication returns 401."""
    response = await client.delete(
        "/authz/tuples",
        json={
            "user_id": "test-user",
            "relation": "member",
            "object_type": "organization",
            "object_id": "test-org",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_batch_write_unauthorized(client: AsyncClient) -> None:
    """Test batch write without authentication returns 401."""
    response = await client.post(
        "/authz/tuples/batch",
        json={
            "tuples": [
                {
                    "user_id": "test-user",
                    "relation": "member",
                    "object_type": "organization",
                    "object_id": "test-org",
                }
            ]
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_roles_unauthorized(client: AsyncClient) -> None:
    """Test get roles without authentication returns 401."""
    response = await client.get("/authz/roles/test-org")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_my_roles_unauthorized(client: AsyncClient) -> None:
    """Test get my roles without authentication returns 401."""
    response = await client.get("/authz/my-roles")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_check_permission_validation_error(client: AsyncClient) -> None:
    """Test permission check with missing fields returns 422."""
    response = await client.post(
        "/authz/check",
        json={"user_id": "test-user"},  # Missing required fields
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_batch_write_empty_tuples(client: AsyncClient) -> None:
    """Test batch write with empty tuples list returns 422."""
    response = await client.post(
        "/authz/tuples/batch",
        json={"tuples": []},
    )
    assert response.status_code == 422


# Tests that require authentication would need a mocked auth context
# In a real test setup, you'd use fixtures to provide authenticated requests


class TestAuthzSchemas:
    """Test authorization schema validation."""

    @pytest.mark.asyncio
    async def test_check_permission_valid_request(self, client: AsyncClient) -> None:
        """Test that valid check permission request is properly validated."""
        from app.schemas.authz import CheckPermissionRequest

        request = CheckPermissionRequest(
            user_id="user-123",
            relation="admin",
            object_type="organization",
            object_id="org-456",
        )
        assert request.user_id == "user-123"
        assert request.relation == "admin"
        assert request.object_type == "organization"
        assert request.object_id == "org-456"

    @pytest.mark.asyncio
    async def test_relationship_tuple_schema(self, client: AsyncClient) -> None:
        """Test RelationshipTuple schema."""
        from app.schemas.authz import RelationshipTuple

        tuple = RelationshipTuple(
            user_id="user-1",
            relation="member",
            object_type="organization",
            object_id="org-1",
        )
        assert tuple.user_id == "user-1"
        assert tuple.relation == "member"

    @pytest.mark.asyncio
    async def test_user_roles_response_schema(self, client: AsyncClient) -> None:
        """Test UserRolesResponse schema."""
        from app.schemas.authz import UserRolesResponse

        response = UserRolesResponse(
            user_id="user-1",
            org_id="org-1",
            roles=["admin", "member"],
            is_admin=True,
            is_member=True,
            is_viewer=True,
        )
        assert response.is_admin is True
        assert "admin" in response.roles
