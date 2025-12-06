from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests
import jwt
from fastapi import HTTPException, Request, status
import structlog

from .config import Settings, get_settings

logger = structlog.get_logger(__name__)


class OAuthValidator:
    """Validate Zitadel-issued OAuth tokens via JWKS."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._jwks: Dict[str, Any] | None = None
        self._jwks_expiry: float = 0

    def _get_jwks(self) -> Dict[str, Any]:
        now = time.time()
        if self._jwks and now < self._jwks_expiry:
            return self._jwks

        try:
            response = requests.get(self._settings.oauth_jwks_url, timeout=5)
            response.raise_for_status()
            data = response.json()
            self._jwks = {item["kid"]: item for item in data.get("keys", [])}
            self._jwks_expiry = now + self._settings.oauth_cache_ttl
            return self._jwks
        except Exception as exc:  # noqa: BLE001
            logger.error("jwks_fetch_failed", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to fetch JWKS for token validation",
            ) from exc

    def _get_signing_key(self, kid: str) -> Dict[str, Any]:
        jwks = self._get_jwks()
        key = jwks.get(kid)
        if not key:
            # Refresh immediately in case key rotated
            self._jwks = None
            jwks = self._get_jwks()
            key = jwks.get(kid)
        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unknown signing key",
            )
        return key

    def validate(self, token: str) -> Dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.DecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token header",
            ) from exc

        key_dict = self._get_signing_key(header.get("kid"))
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_dict)

        options = {"verify_aud": bool(self._settings.oauth_audience)}

        try:
            claims = jwt.decode(
                token,
                key=public_key,
                algorithms=[header.get("alg", "RS256")],
                audience=self._settings.oauth_audience,
                issuer=self._settings.oauth_issuer,
                options=options,
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token validation failed",
            ) from exc

        required_scope = self._settings.oauth_required_scope
        if required_scope:
            scopes = claims.get("scope", "")
            scope_set = set(scopes.split())
            if required_scope not in scope_set:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Missing required scope",
                )

        return claims


_validator = OAuthValidator(get_settings())


def require_oauth_token(request: Request) -> Dict[str, Any]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = auth_header.split(" ", 1)[1].strip()
    claims = _validator.validate(token)
    request.state.principal = claims.get("sub")
    request.state.oauth_scopes = claims.get("scope", "")
    return claims

