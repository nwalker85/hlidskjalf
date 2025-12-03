from __future__ import annotations

import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class RoleMapping:
    name: str
    gitlab_access_level: int


@dataclass
class PermissionMapping:
    roles: Dict[str, RoleMapping]
    service_accounts: Dict[str, RoleMapping]

    @classmethod
    def load(cls, path: str | Path) -> "PermissionMapping":
        data = yaml.safe_load(Path(path).read_text())
        roles = {
            name: RoleMapping(name=name, gitlab_access_level=entry["gitlab_access_level"])
            for name, entry in data.get("roles", {}).items()
        }
        service_accounts = {
            name: RoleMapping(name=name, gitlab_access_level=entry["gitlab_access_level"])
            for name, entry in data.get("service_accounts", {}).items()
        }
        return cls(roles=roles, service_accounts=service_accounts)

    def resolve_role(self, role: str) -> Optional[RoleMapping]:
        return self.roles.get(role)

    def resolve_service_account(self, name: str) -> Optional[RoleMapping]:
        return self.service_accounts.get(name)

