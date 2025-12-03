from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class PermissionSyncConfig:
    zitadel_base_url: str
    zitadel_project_id: str
    zitadel_token: str
    gitlab_base_url: str
    gitlab_group_id: int
    gitlab_provider: str
    gitlab_token: str
    mapping_path: str
    state_file: str
    run_interval_seconds: int
    dry_run: bool
    localstack_endpoint: Optional[str] = None
    zitadel_audience: str = "openid_connect"

    @classmethod
    def from_env(
        cls,
        zitadel_token: str,
        gitlab_token: str,
        mapping_path: str,
        state_file: str,
    ) -> "PermissionSyncConfig":
        return cls(
            zitadel_base_url=os.getenv("PERM_SYNC_ZITADEL_BASE_URL", "https://zitadel.ravenhelm.test"),
            zitadel_project_id=os.environ["PERM_SYNC_ZITADEL_PROJECT_ID"],
            zitadel_token=zitadel_token,
            gitlab_base_url=os.getenv("PERM_SYNC_GITLAB_BASE_URL", "https://gitlab.ravenhelm.test/api/v4"),
            gitlab_group_id=int(os.environ.get("PERM_SYNC_GITLAB_GROUP_ID", "3")),
            gitlab_provider=os.getenv("PERM_SYNC_GITLAB_PROVIDER", "openid_connect"),
            gitlab_token=gitlab_token,
            mapping_path=mapping_path,
            state_file=state_file,
            run_interval_seconds=int(os.getenv("PERM_SYNC_INTERVAL_SECONDS", "900")),
            dry_run=os.getenv("PERM_SYNC_DRY_RUN", "false").lower() == "true",
            localstack_endpoint=os.getenv("LOCALSTACK_ENDPOINT"),
            zitadel_audience=os.getenv("PERM_SYNC_ZITADEL_PROVIDER", "openid_connect"),
        )

