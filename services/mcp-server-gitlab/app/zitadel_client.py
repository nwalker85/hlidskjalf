from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
import structlog

from .config import Settings

logger = structlog.get_logger(__name__)


class ZitadelService:
    """Lightweight Zitadel management client (REST)."""

    def __init__(self, settings: Settings, token: str):
        self._settings = settings
        self._token = token
        self._client = httpx.Client(
            base_url=settings.zitadel_base_url.rstrip("/"),
            verify=settings.zitadel_verify_ssl,
            timeout=httpx.Timeout(15.0, connect=5.0),
        )

    # --------------------------------------------------------------------- #
    def _request(
        self, method: str, path: str, *, json_body: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        response = self._client.request(
            method,
            path,
            json=json_body,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "zitadel_http_error",
                method=method,
                path=path,
                status=exc.response.status_code,
                body=exc.response.text,
            )
            raise
        return response.json()

    # --------------------------------------------------------------------- #
    def _get_user_id(self, user_id: str | None, email: str | None) -> str:
        if user_id:
            return user_id
        if not email:
            raise ValueError("user_id or email is required")

        payload = {
            "queries": [
                {
                    "emailQuery": {
                        "emailAddress": email,
                        "method": "TEXT_QUERY_METHOD_EQUALS",
                    }
                }
            ]
        }
        response = self._request("POST", "/management/v1/users/_search", json_body=payload)
        results = response.get("result") or []
        if not results:
            raise ValueError(f"No Zitadel user found for email {email}")
        return results[0]["id"]

    # --------------------------------------------------------------------- #
    def list_user_roles(
        self, *, user_id: str | None = None, email: str | None = None
    ) -> Dict[str, Any]:
        resolved_id = self._get_user_id(user_id, email)
        response = self._request(
            "GET",
            f"/management/v1/users/{resolved_id}/grants",
        )
        grants = response.get("result", [])
        project_grants = [
            grant
            for grant in grants
            if grant.get("projectId") == self._settings.zitadel_project_id
        ]
        roles = []
        for grant in project_grants:
            roles.extend(grant.get("roleKeys", []))
        return {"user_id": resolved_id, "roles": sorted(set(roles))}

    # --------------------------------------------------------------------- #
    def assign_roles(
        self,
        *,
        role_keys: List[str],
        user_id: str | None = None,
        email: str | None = None,
    ) -> Dict[str, Any]:
        if not role_keys:
            raise ValueError("role_keys is required")
        resolved_id = self._get_user_id(user_id, email)
        payload = {
            "userId": resolved_id,
            "projectId": self._settings.zitadel_project_id,
            "roleKeys": role_keys,
        }
        self._request(
            "POST",
            f"/management/v1/users/{resolved_id}/grants",
            json_body=payload,
        )
        return {"status": "granted", "user_id": resolved_id, "roles": role_keys}

    # --------------------------------------------------------------------- #
    def create_service_account(
        self,
        *,
        user_name: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        role_keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "userName": user_name,
            "name": display_name or user_name,
            "description": description or "",
            "accessTokenType": "ACCESS_TOKEN_TYPE_JWT",
        }
        response = self._request("POST", "/management/v1/users/machine", json_body=payload)
        machine_id = response.get("userId")
        if not machine_id:
            raise ValueError("Zitadel did not return a userId for the new service account")

        # Generate PAT so callers can authenticate immediately.
        pat_response = self._request(
            "POST",
            f"/management/v1/users/{machine_id}/pats",
            json_body={"name": f"{user_name}-pat", "scopes": ["openid", "profile"]},
        )
        token = pat_response.get("token")

        assigned_roles: List[str] = []
        if role_keys:
            self.assign_roles(user_id=machine_id, role_keys=role_keys)
            assigned_roles = role_keys

        return {
            "user_id": machine_id,
            "pat_token": token,
            "roles": assigned_roles,
        }

