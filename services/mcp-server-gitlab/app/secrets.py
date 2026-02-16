from __future__ import annotations

import json
from typing import Any, Dict

import boto3
import structlog

from .config import Settings

logger = structlog.get_logger(__name__)


class SecretFetcher:
    """Small helper around AWS Secrets Manager / LocalStack."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = boto3.client(
            "secretsmanager",
            region_name=settings.aws_region,
            endpoint_url=settings.localstack_endpoint,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    def get_secret(self, secret_name: str) -> Dict[str, Any]:
        try:
            response = self._client.get_secret_value(SecretId=secret_name)
            secret_string = response.get("SecretString") or "{}"
            return json.loads(secret_string)
        except Exception as exc:  # noqa: BLE001
            logger.warning("secret_fetch_failed", secret_name=secret_name, error=str(exc))
            return {}


def resolve_gitlab_tokens(settings: Settings) -> tuple[str | None, str | None]:
    """Return (api_token, wiki_token) using env vars or secrets manager."""
    if settings.gitlab_token:
        return settings.gitlab_token, settings.gitlab_wiki_token

    fetcher = SecretFetcher(settings)
    data = fetcher.get_secret(settings.gitlab_secret_name)
    api_token = data.get("token")
    wiki_token = data.get("wiki_token") or api_token
    return api_token, wiki_token


def resolve_zitadel_credentials(settings: Settings) -> Dict[str, Any]:
    """Return Zitadel service account info."""
    if settings.zitadel_service_account_token:
        return {
            "token": settings.zitadel_service_account_token,
            "id": None,
        }

    fetcher = SecretFetcher(settings)
    data = fetcher.get_secret(settings.zitadel_service_account_secret)
    return {
        "token": data.get("token"),
        "id": data.get("id"),
    }

