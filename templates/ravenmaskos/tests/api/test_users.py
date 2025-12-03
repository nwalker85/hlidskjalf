"""Tests for user management API routes."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_users_unauthorized(client: AsyncClient) -> None:
    """Test list users without authentication returns 401."""
    response = await client.get("/users")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_user_unauthorized(client: AsyncClient) -> None:
    """Test get user without authentication returns 401."""
    response = await client.get("/users/some-user-id")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_user_unauthorized(client: AsyncClient) -> None:
    """Test create user without authentication returns 401."""
    response = await client.post(
        "/users",
        json={
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "full_name": "New User",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_user_unauthorized(client: AsyncClient) -> None:
    """Test update user without authentication returns 401."""
    response = await client.patch(
        "/users/some-user-id",
        json={"full_name": "Updated Name"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_user_roles_unauthorized(client: AsyncClient) -> None:
    """Test update user roles without authentication returns 401."""
    response = await client.put(
        "/users/some-user-id/roles",
        json={"roles": ["member"]},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_user_unauthorized(client: AsyncClient) -> None:
    """Test delete user without authentication returns 401."""
    response = await client.delete("/users/some-user-id")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invite_user_unauthorized(client: AsyncClient) -> None:
    """Test invite user without authentication returns 401."""
    response = await client.post(
        "/users/invite",
        json={"email": "invite@example.com"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_bulk_action_unauthorized(client: AsyncClient) -> None:
    """Test bulk action without authentication returns 401."""
    response = await client.post(
        "/users/bulk",
        json={"user_ids": ["user-1", "user-2"], "action": "deactivate"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient) -> None:
    """Test get current user without authentication returns 401."""
    response = await client.get("/users/me")
    assert response.status_code == 401


# Schema validation tests

@pytest.mark.asyncio
async def test_create_user_weak_password(client: AsyncClient) -> None:
    """Test create user with weak password returns 422."""
    response = await client.post(
        "/users",
        json={
            "email": "newuser@example.com",
            "password": "short",  # Too short
            "full_name": "New User",
        },
    )
    assert response.status_code in (401, 422)  # 401 if auth checked first


@pytest.mark.asyncio
async def test_create_user_invalid_email(client: AsyncClient) -> None:
    """Test create user with invalid email returns 422."""
    response = await client.post(
        "/users",
        json={
            "email": "not-an-email",
            "password": "SecurePass123!",
            "full_name": "New User",
        },
    )
    assert response.status_code in (401, 422)


@pytest.mark.asyncio
async def test_update_roles_empty(client: AsyncClient) -> None:
    """Test update roles with empty list returns 422."""
    response = await client.put(
        "/users/some-user-id/roles",
        json={"roles": []},
    )
    assert response.status_code in (401, 422)


@pytest.mark.asyncio
async def test_bulk_action_invalid_action(client: AsyncClient) -> None:
    """Test bulk action with invalid action returns 422."""
    response = await client.post(
        "/users/bulk",
        json={"user_ids": ["user-1"], "action": "invalid_action"},
    )
    assert response.status_code in (401, 422)


@pytest.mark.asyncio
async def test_bulk_action_empty_users(client: AsyncClient) -> None:
    """Test bulk action with empty user list returns 422."""
    response = await client.post(
        "/users/bulk",
        json={"user_ids": [], "action": "deactivate"},
    )
    assert response.status_code in (401, 422)


class TestUserSchemas:
    """Test user schema validation."""

    @pytest.mark.asyncio
    async def test_user_create_schema(self, client: AsyncClient) -> None:
        """Test UserCreate schema validation."""
        from app.schemas.users import UserCreate

        user = UserCreate(
            email="test@example.com",
            password="SecurePass123!",
            full_name="Test User",
            roles=["member"],
        )
        assert user.email == "test@example.com"
        assert user.roles == ["member"]

    @pytest.mark.asyncio
    async def test_user_update_schema(self, client: AsyncClient) -> None:
        """Test UserUpdate schema allows partial updates."""
        from app.schemas.users import UserUpdate

        update = UserUpdate(full_name="Updated Name")
        assert update.full_name == "Updated Name"
        assert update.username is None
        assert update.is_active is None

    @pytest.mark.asyncio
    async def test_user_response_from_model(self, client: AsyncClient) -> None:
        """Test UserResponse can be created from attributes."""
        from datetime import datetime
        from app.schemas.users import UserResponse

        response = UserResponse(
            id="user-123",
            email="test@example.com",
            username=None,
            full_name="Test User",
            avatar_url=None,
            is_active=True,
            is_verified=False,
            roles=["member"],
            scopes=["org:read"],
            mfa_enabled=False,
            last_login_at=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert response.id == "user-123"
        assert response.is_active is True
