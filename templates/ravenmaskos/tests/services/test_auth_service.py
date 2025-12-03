"""Tests for authentication service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.auth_service import (
    AuthError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    UserInactiveError,
    UserLockedError,
    _generate_org_slug,
)
from app.schemas.auth import LoginRequest, RegisterRequest


def test_generate_org_slug_basic() -> None:
    """Test slug generation from org name."""
    slug = _generate_org_slug("My Company")
    assert slug.startswith("my-company-")
    assert len(slug) == len("my-company-") + 8  # 8 char hex suffix


def test_generate_org_slug_special_chars() -> None:
    """Test slug generation removes special characters."""
    slug = _generate_org_slug("Company & Sons, Inc.")
    assert "&" not in slug
    assert "," not in slug
    assert "." not in slug


def test_generate_org_slug_truncates_long_names() -> None:
    """Test slug generation truncates long names."""
    long_name = "A" * 100
    slug = _generate_org_slug(long_name)
    # Should be truncated to 50 chars + hyphen + 8 char suffix
    assert len(slug) <= 59


def test_invalid_credentials_error() -> None:
    """Test InvalidCredentialsError has correct properties."""
    error = InvalidCredentialsError()
    assert error.code == "invalid_credentials"
    assert "Invalid" in error.message


def test_user_locked_error_with_until() -> None:
    """Test UserLockedError includes lock time when provided."""
    from datetime import datetime, timezone

    until = datetime.now(timezone.utc)
    error = UserLockedError(until)
    assert "locked until" in error.message
    assert error.code == "user_locked"


def test_user_locked_error_without_until() -> None:
    """Test UserLockedError works without lock time."""
    error = UserLockedError()
    assert error.code == "user_locked"
    assert "locked" in error.message.lower()


def test_email_already_exists_error() -> None:
    """Test EmailAlreadyExistsError has correct properties."""
    error = EmailAlreadyExistsError()
    assert error.code == "email_exists"


def test_invalid_token_error() -> None:
    """Test InvalidTokenError has correct properties."""
    error = InvalidTokenError()
    assert error.code == "invalid_token"


def test_user_inactive_error() -> None:
    """Test UserInactiveError has correct properties."""
    error = UserInactiveError()
    assert error.code == "user_inactive"


class TestLoginRequest:
    """Tests for LoginRequest schema."""

    def test_valid_login_request(self) -> None:
        """Test valid login request."""
        request = LoginRequest(email="user@example.com", password="password123")
        assert request.email == "user@example.com"
        assert request.password == "password123"

    def test_login_request_invalid_email(self) -> None:
        """Test login request with invalid email."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LoginRequest(email="not-an-email", password="password123")

    def test_login_request_empty_password(self) -> None:
        """Test login request with empty password."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LoginRequest(email="user@example.com", password="")


class TestRegisterRequest:
    """Tests for RegisterRequest schema."""

    def test_valid_register_request(self) -> None:
        """Test valid register request."""
        request = RegisterRequest(
            email="user@example.com",
            password="securepassword123",
            full_name="Test User",
            org_name="Test Org",
        )
        assert request.email == "user@example.com"
        assert request.full_name == "Test User"
        assert request.org_name == "Test Org"

    def test_register_request_without_org_name(self) -> None:
        """Test register request without org name is valid."""
        request = RegisterRequest(
            email="user@example.com",
            password="securepassword123",
            full_name="Test User",
        )
        assert request.org_name is None

    def test_register_request_short_password(self) -> None:
        """Test register request with short password fails."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@example.com",
                password="short",  # Less than 8 chars
                full_name="Test User",
            )

    def test_register_request_empty_name(self) -> None:
        """Test register request with empty name fails."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@example.com",
                password="securepassword123",
                full_name="",  # Empty
            )
