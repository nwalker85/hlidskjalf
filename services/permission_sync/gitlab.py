from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx

log = logging.getLogger(__name__)


@dataclass
class GitLabUser:
    id: int
    username: str
    extern_uid: Optional[str]
    email: Optional[str]


@dataclass
class GitLabMember:
    user: GitLabUser
    access_level: int


class GitLabClient:
    def __init__(self, base_url: str, token: str, group_id: int, provider: str):
        self.base_url = base_url.rstrip("/")
        self.group_id = group_id
        self.provider = provider
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"PRIVATE-TOKEN": token},
            timeout=15.0,
            verify=False,
        )

    def list_group_members(self) -> Dict[int, GitLabMember]:
        resp = self._client.get(f"/groups/{self.group_id}/members/all")
        resp.raise_for_status()
        members: Dict[int, GitLabMember] = {}
        for entry in resp.json():
            user = GitLabUser(
                id=entry["id"],
                username=entry["username"],
                extern_uid=entry.get("extern_uid"),
                email=entry.get("email"),
            )
            members[user.id] = GitLabMember(user=user, access_level=entry["access_level"])
        return members

    def find_user_by_external_id(self, extern_uid: str) -> Optional[GitLabUser]:
        params = {"extern_uid": extern_uid, "provider": self.provider}
        resp = self._client.get("/users", params=params)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        entry = data[0]
        return GitLabUser(
            id=entry["id"],
            username=entry["username"],
            extern_uid=entry.get("extern_uid"),
            email=entry.get("email"),
        )

    def add_member(self, user_id: int, access_level: int) -> None:
        log.info("Granting GitLab access level %s to user %s", access_level, user_id)
        payload = {"user_id": user_id, "access_level": access_level}
        resp = self._client.post(f"/groups/{self.group_id}/members", json=payload)
        if resp.status_code == 201:
            return
        if resp.status_code == 409:
            # Member already exists; downgrade/upgrade with PUT
            self.update_member(user_id, access_level)
            return
        resp.raise_for_status()

    def update_member(self, user_id: int, access_level: int) -> None:
        log.info("Updating GitLab access level for user %s -> %s", user_id, access_level)
        payload = {"access_level": access_level}
        resp = self._client.put(f"/groups/{self.group_id}/members/{user_id}", json=payload)
        resp.raise_for_status()

    def remove_member(self, user_id: int) -> None:
        log.info("Removing GitLab access for user %s", user_id)
        resp = self._client.delete(f"/groups/{self.group_id}/members/{user_id}")
        if resp.status_code not in (200, 204):
            resp.raise_for_status()

