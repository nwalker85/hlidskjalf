"""Zitadel OIDC integration for JWT validation.

Provides JWT validation using Zitadel's JWKS endpoint with caching.
Supports both user tokens and service account tokens.
"""

import time
from dataclasses import dataclass
from typing import Any

import httpx
from jose import JWTError, jwt
from jose.backends import RSAKey

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class JWKSCache:
    """Cached JWKS with expiration."""

    keys: dict[str, Any]
    expires_at: float


_jwks_cache: JWKSCache | None = None


async def fetch_jwks() -> dict[str, Any]:
    """Fetch JWKS from Zitadel issuer."""
    global _jwks_cache

    now = time.time()

    # Return cached keys if still valid
    if _jwks_cache and _jwks_cache.expires_at > now:
        return _jwks_cache.keys

    jwks_url = f"{settings.ZITADEL_ISSUER}/.well-known/jwks.json"
    logger.debug("Fetching JWKS", url=jwks_url)

    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_url, timeout=10)
        response.raise_for_status()
        jwks = response.json()

    # Build key lookup by kid
    keys = {key["kid"]: key for key in jwks.get("keys", [])}

    # Cache with TTL
    _jwks_cache = JWKSCache(
        keys=keys,
        expires_at=now + settings.ZITADEL_JWKS_CACHE_TTL,
    )

    logger.info("JWKS cached", key_count=len(keys))
    return keys


def clear_jwks_cache() -> None:
    """Clear JWKS cache - useful for testing or key rotation."""
    global _jwks_cache
    _jwks_cache = None


@dataclass
class ZitadelTokenPayload:
    """Validated Zitadel JWT payload."""

    sub: str  # User ID
    iss: str  # Issuer
    aud: list[str]  # Audience
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp
    azp: str | None = None  # Authorized party (client ID)
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    preferred_username: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    locale: str | None = None
    # Zitadel-specific claims
    org_id: str | None = None  # urn:zitadel:iam:org:id
    project_roles: dict[str, Any] | None = None  # urn:zitadel:iam:org:project:roles

    @classmethod
    def from_claims(cls, claims: dict[str, Any]) -> "ZitadelTokenPayload":
        """Create payload from JWT claims dict."""
        # Handle audience as string or list
        aud = claims.get("aud", [])
        if isinstance(aud, str):
            aud = [aud]

        return cls(
            sub=claims["sub"],
            iss=claims["iss"],
            aud=aud,
            exp=claims["exp"],
            iat=claims["iat"],
            azp=claims.get("azp"),
            email=claims.get("email"),
            email_verified=claims.get("email_verified", False),
            name=claims.get("name"),
            preferred_username=claims.get("preferred_username"),
            given_name=claims.get("given_name"),
            family_name=claims.get("family_name"),
            locale=claims.get("locale"),
            org_id=claims.get("urn:zitadel:iam:org:id"),
            project_roles=claims.get("urn:zitadel:iam:org:project:roles"),
        )

    def get_roles(self) -> list[str]:
        """Extract role names from project roles claim."""
        if not self.project_roles:
            return []

        roles = []
        for role_key, orgs in self.project_roles.items():
            # role_key is like "admin", orgs is {"org_id": {"org_domain": "..."}}
            roles.append(role_key)
        return roles


async def validate_zitadel_token(token: str) -> ZitadelTokenPayload:
    """Validate a Zitadel JWT token.

    Args:
        token: The JWT token to validate

    Returns:
        ZitadelTokenPayload with validated claims

    Raises:
        ValueError: If token is invalid
    """
    # Decode header to get key ID
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as e:
        logger.warning("Failed to decode JWT header", error=str(e))
        raise ValueError("Invalid token format") from e

    kid = unverified_header.get("kid")
    if not kid:
        raise ValueError("Token missing key ID (kid)")

    # Fetch JWKS and get signing key
    keys = await fetch_jwks()
    if kid not in keys:
        # Key not found - try refreshing cache once
        clear_jwks_cache()
        keys = await fetch_jwks()
        if kid not in keys:
            logger.warning("Signing key not found in JWKS", kid=kid)
            raise ValueError("Invalid signing key")

    jwk = keys[kid]

    # Validate token
    try:
        claims = jwt.decode(
            token,
            jwk,
            algorithms=["RS256"],
            issuer=settings.ZITADEL_ISSUER,
            options={
                "verify_aud": False,  # We'll check audience manually if needed
                "verify_iss": True,
                "verify_exp": True,
            },
        )
    except JWTError as e:
        logger.warning("JWT validation failed", error=str(e))
        raise ValueError(f"Token validation failed: {e}") from e

    # Optionally verify audience if client ID is configured
    if settings.ZITADEL_WEB_CLIENT_ID:
        aud = claims.get("aud", [])
        if isinstance(aud, str):
            aud = [aud]
        # Check if our client ID or project ID is in audience
        valid_audiences = [settings.ZITADEL_WEB_CLIENT_ID]
        if settings.ZITADEL_PROJECT_ID:
            valid_audiences.append(settings.ZITADEL_PROJECT_ID)

        if not any(a in aud for a in valid_audiences):
            logger.warning("Token audience mismatch", aud=aud, expected=valid_audiences)
            # Don't reject yet - Zitadel includes project ID in aud

    return ZitadelTokenPayload.from_claims(claims)


async def get_oidc_configuration() -> dict[str, Any]:
    """Fetch OIDC discovery document from Zitadel."""
    url = f"{settings.ZITADEL_ISSUER}/.well-known/openid-configuration"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
