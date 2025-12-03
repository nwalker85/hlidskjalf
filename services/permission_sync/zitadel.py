from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import httpx

log = logging.getLogger(__name__)


@dataclass
class ZitadelProjectGrant:
    user_id: str
    display_name: Optional[str]
    email: Optional[str]
    role_keys: List[str]
    is_machine: bool


class ZitadelClient:
    def __init__(self, base_url: str, token: str, project_id: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.project_id = project_id
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=15.0,
            verify=False,  # Traefik terminates TLS; internal services validate via mkcert
        )

    def list_project_grants(self) -> List[ZitadelProjectGrant]:
        """Fetch all grants for the configured project."""
        body = {
            "queries": [
                {
                    "projectQuery": {
                        "projectIdQuery": {"projectId": self.project_id},
                    }
                }
            ],
            "limit": 500,
        }
        resp = self._client.post("/management/v1/projects/_search_grants", json=body)
        resp.raise_for_status()
        results = resp.json().get("result", [])
        grants: List[ZitadelProjectGrant] = []
        for entry in results:
            detail = entry.get("grantDetails", {})
            grants.append(
                ZitadelProjectGrant(
                    user_id=entry.get("userId"),
                    display_name=detail.get("displayName"),
                    email=detail.get("email"),
                    role_keys=entry.get("roleKeys", []),
                    is_machine=detail.get("isMachine", False),
                )
            )
        log.debug("Fetched %s grants from Zitadel", len(grants))
        return grants

