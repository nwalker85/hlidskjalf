"""
Lightweight Secrets Manager helper for Bifrost Gateway.

In development we talk to LocalStack (http://localstack:4566) using dummy
credentials. In production we rely on the container IAM role or explicitly
provided AWS credentials.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Optional

import boto3
import structlog
from botocore.config import Config
from botocore.exceptions import ClientError

logger = structlog.get_logger(__name__)


class SecretsHelper:
    """Tiny wrapper around AWS Secrets Manager / LocalStack."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        if endpoint_url is None:
            endpoint_url = os.environ.get("AWS_ENDPOINT_URL")

        if endpoint_url and "localstack" in endpoint_url:
            aws_access_key_id = aws_access_key_id or "test"
            aws_secret_access_key = aws_secret_access_key or "test"

        config = Config(
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=10,
        )

        self._client = boto3.client(
            "secretsmanager",
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            config=config,
        )

    def get_secret(self, name: str) -> str:
        """Return the plain secret string."""
        try:
            response = self._client.get_secret_value(SecretId=name)
            return response["SecretString"]
        except ClientError as exc:  # pragma: no cover - just log & bubble
            logger.error("secrets_fetch_failed", secret=name, error=str(exc))
            raise

    def get_secret_json(self, name: str) -> dict[str, Any]:
        """Return the secret parsed as JSON."""
        value = self.get_secret(name)
        return json.loads(value)


@lru_cache
def get_secrets_helper(
    endpoint_url: Optional[str] = None,
    region_name: str = "us-east-1",
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> SecretsHelper:
    return SecretsHelper(
        endpoint_url=endpoint_url,
        region_name=region_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

