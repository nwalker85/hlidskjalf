from __future__ import annotations

import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional

from .config import PermissionSyncConfig
from .gitlab import GitLabClient, GitLabMember
from .mapping import PermissionMapping
from .state import SyncState
from .zitadel import ZitadelClient, ZitadelProjectGrant

log = logging.getLogger(__name__)


class PermissionSyncService:
    def __init__(self, config: PermissionSyncConfig):
        self.config = config
        self.mapping = PermissionMapping.load(config.mapping_path)
        self.state_path = Path(config.state_file)
        self.state = SyncState.load(self.state_path)
        self.zitadel = ZitadelClient(
            base_url=config.zitadel_base_url,
            token=config.zitadel_token,
            project_id=config.zitadel_project_id,
        )
        self.gitlab = GitLabClient(
            base_url=config.gitlab_base_url,
            token=config.gitlab_token,
            group_id=config.gitlab_group_id,
            provider=config.gitlab_provider,
        )

    def run_forever(self) -> None:
        interval = self.config.run_interval_seconds
        while True:
            self.sync_once(dry_run=self.config.dry_run)
            time.sleep(interval)

    def sync_once(self, dry_run: bool = False) -> None:
        log.info("Starting permission sync (dry_run=%s)", dry_run)
        grants = self.zitadel.list_project_grants()
        desired = self._build_desired_memberships(grants)
        current_members = self.gitlab.list_group_members()
        plan = self._compute_plan(desired, current_members)
        self._apply_plan(plan, dry_run=dry_run)
        log.info("Permission sync complete (added=%s, updated=%s, removed=%s)", *plan.summary())

    def _build_desired_memberships(self, grants: list[ZitadelProjectGrant]) -> Dict[str, int]:
        """
        Returns mapping of Zitadel user IDs to desired GitLab access level.
        """
        desired: Dict[str, int] = {}
        for grant in grants:
            highest = 0
            for role in grant.role_keys:
                mapping = self.mapping.resolve_role(role)
                if mapping:
                    highest = max(highest, mapping.gitlab_access_level)
            if grant.is_machine:
                sa_mapping = self.mapping.resolve_service_account(grant.display_name or "")
                if sa_mapping:
                    highest = max(highest, sa_mapping.gitlab_access_level)
            if highest > 0:
                desired[grant.user_id] = highest
        return desired

    def _compute_plan(
        self,
        desired: Dict[str, int],
        current_members: Dict[int, GitLabMember],
    ) -> "SyncPlan":
        plan = SyncPlan()
        managed = self.state.managed_users
        # Add/update desired members
        for zitadel_user_id, access_level in desired.items():
            gitlab_user = self.gitlab.find_user_by_external_id(zitadel_user_id)
            if not gitlab_user:
                log.warning("Zitadel user %s has not logged into GitLab yet; skipping", zitadel_user_id)
                continue
            managed[zitadel_user_id] = gitlab_user.id
            member = current_members.get(gitlab_user.id)
            if not member:
                plan.to_add.append((gitlab_user.id, access_level))
            elif member.access_level != access_level:
                plan.to_update.append((gitlab_user.id, access_level))

        # Removals (only for users we manage)
        for zitadel_user_id, gitlab_user_id in list(managed.items()):
            if zitadel_user_id not in desired:
                plan.to_remove.append(gitlab_user_id)
                managed.pop(zitadel_user_id, None)
            elif gitlab_user_id not in current_members:
                managed.pop(zitadel_user_id, None)

        return plan

    def _apply_plan(self, plan: "SyncPlan", dry_run: bool) -> None:
        if dry_run:
            log.info(
                "[DRY RUN] Would add=%s, update=%s, remove=%s",
                plan.to_add,
                plan.to_update,
                plan.to_remove,
            )
            return
        for user_id, level in plan.to_add:
            self.gitlab.add_member(user_id, level)
        for user_id, level in plan.to_update:
            self.gitlab.update_member(user_id, level)
        for user_id in plan.to_remove:
            self.gitlab.remove_member(user_id)
        self.state.save(self.state_path)


class SyncPlan:
    def __init__(self) -> None:
        self.to_add: list[tuple[int, int]] = []
        self.to_update: list[tuple[int, int]] = []
        self.to_remove: list[int] = []
        self.desired: set[int] = set()

    def summary(self) -> tuple[int, int, int]:
        return len(self.to_add), len(self.to_update), len(self.to_remove)

