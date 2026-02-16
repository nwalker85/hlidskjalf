from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class SyncState:
    managed_users: Dict[str, int] = field(default_factory=dict)  # extern_uid -> gitlab_user_id

    @classmethod
    def load(cls, path: Path) -> "SyncState":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        return cls(managed_users=data.get("managed_users", {}))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"managed_users": self.managed_users}, indent=2))

