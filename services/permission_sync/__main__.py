from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from .config import PermissionSyncConfig
from .secrets import SecretProvider
from .service import PermissionSyncService

logging.basicConfig(
    level=os.getenv("PERM_SYNC_LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("permission_sync")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Zitadel → GitLab permission sync")
    parser.add_argument("--run-once", action="store_true", help="Run a single sync pass and exit")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes (overrides env)")
    parser.add_argument("--mapping", default="config/permission-sync/mapping.yaml", help="Role mapping YAML")
    parser.add_argument(
        "--state-file",
        default="data/permission-sync-state.json",
        help="Path to local state file (tracks managed members)",
    )
    parser.add_argument("--zitadel-secret", help="Secrets Manager ID for Zitadel token")
    parser.add_argument("--gitlab-secret", help="Secrets Manager ID for GitLab PAT")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    provider = SecretProvider(localstack_endpoint=os.getenv("LOCALSTACK_ENDPOINT"))
    zitadel_token = provider.fetch(args.zitadel_secret or "", env_fallback="PERM_SYNC_ZITADEL_TOKEN")
    gitlab_token = provider.fetch(args.gitlab_secret or "", env_fallback="PERM_SYNC_GITLAB_TOKEN")

    config = PermissionSyncConfig.from_env(
        zitadel_token=zitadel_token,
        gitlab_token=gitlab_token,
        mapping_path=args.mapping,
        state_file=args.state_file,
    )
    if args.dry_run:
        config.dry_run = True

    service = PermissionSyncService(config)
    if args.run_once:
        service.sync_once(dry_run=config.dry_run)
    else:
        service.run_forever()


if __name__ == "__main__":
    main()

