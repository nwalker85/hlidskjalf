from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig


@dataclass
class SecretProvider:
    localstack_endpoint: Optional[str] = None

    def _client(self):
        return boto3.client(
            "secretsmanager",
            endpoint_url=self.localstack_endpoint,
            config=BotoConfig(retries={"max_attempts": 3}),
        )

    def fetch(self, secret_name: str, env_fallback: Optional[str] = None) -> str:
        if secret_name:
            secret_string = self._client().get_secret_value(SecretId=secret_name)["SecretString"]
            try:
                payload = json.loads(secret_string)
                # Return first value if JSON object
                if isinstance(payload, dict) and "value" in payload:
                    return payload["value"]
            except json.JSONDecodeError:
                pass
            return secret_string
        if env_fallback:
            value = os.getenv(env_fallback)
            if not value:
                raise RuntimeError(f"Environment variable {env_fallback} not set")
            return value
        raise RuntimeError("No secret source provided")

