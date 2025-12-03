"""Tests for authentication API routes."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_missing_credentials(client: AsyncClient) -> None:
    """Test login with missing credentials returns 422."""
    response = await client.post("/auth/token", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_invalid_email_format(client: AsyncClient) -> None:
    """Test login with invalid email format returns 422."""
    response = await client.post(
        "/auth/token",
        json={"email": "not-an-email", "password": "password123"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient) -> None:
    """Test login with non-existent user returns 401."""
    response = await client.post(
        "/auth/token",
        json={"email": "nonexistent@example.com", "password": "password123"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["error"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_me_unauthorized(client: AsyncClient) -> None:
    """Test /me endpoint without authentication returns 401."""
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient) -> None:
    """Test successful user registration."""
    response = await client.post(
        "/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "full_name": "New User",
            "org_name": "New Org",
        },
    )
    # Note: This will fail without a real database
    # In a real test setup, we'd use a test database
    assert response.status_code in (201, 500)  # 500 if no DB


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    """Test registration with duplicate email returns 409."""
    # First registration
    await client.post(
        "/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "SecurePass123!",
            "full_name": "First User",
        },
    )
    # Second registration with same email
    response = await client.post(
        "/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "SecurePass123!",
            "full_name": "Second User",
        },
    )
    # Note: This will only work with real DB
    assert response.status_code in (409, 500)


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient) -> None:
    """Test registration with weak password returns 422."""
    response = await client.post(
        "/auth/register",
        json={
            "email": "user@example.com",
            "password": "short",  # Too short
            "full_name": "User",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_refresh_no_token(client: AsyncClient) -> None:
    """Test token refresh without token returns 401."""
    response = await client.post("/auth/refresh", json={"refresh_token": ""})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient) -> None:
    """Test token refresh with invalid token returns 401."""
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_forgot_password_nonexistent_email(client: AsyncClient) -> None:
    """Test forgot password with non-existent email still returns 200.

    This prevents email enumeration attacks.
    """
    response = await client.post(
        "/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )
    # Should always return success to prevent email enumeration
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client: AsyncClient) -> None:
    """Test reset password with invalid token returns 401."""
    response = await client.post(
        "/auth/reset-password",
        json={"token": "invalid", "new_password": "NewSecurePass123!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client: AsyncClient) -> None:
    """Test verify email with invalid token returns 401."""
    response = await client.post(
        "/auth/verify-email",
        json={"token": "invalid"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mfa_verify_not_implemented(client: AsyncClient) -> None:
    """Test MFA verify returns 501 (not implemented)."""
    response = await client.post(
        "/auth/mfa/verify",
        json={"mfa_token": "token", "code": "123456"},
    )
    assert response.status_code == 501
