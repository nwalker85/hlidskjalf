import json
from functools import lru_cache
from typing import Any

import aioboto3
from botocore.config import Config

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_boto_config() -> dict[str, Any]:
    config: dict[str, Any] = {
        "region_name": settings.AWS_REGION,
        "config": Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=5,
            read_timeout=10,
        ),
    }

    if settings.AWS_ACCESS_KEY_ID:
        config["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
    if settings.AWS_SECRET_ACCESS_KEY:
        config["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    if settings.AWS_ENDPOINT_URL:
        config["endpoint_url"] = settings.AWS_ENDPOINT_URL

    return config


@lru_cache
def get_session() -> aioboto3.Session:
    return aioboto3.Session()


async def get_secret(secret_name: str) -> dict[str, Any]:
    session = get_session()
    config = get_boto_config()

    async with session.client("secretsmanager", **config) as client:
        try:
            response = await client.get_secret_value(SecretId=secret_name)
            if "SecretString" in response:
                return json.loads(response["SecretString"])
            logger.warning("Secret is binary, not string", secret=secret_name)
            return {}
        except client.exceptions.ResourceNotFoundException:
            logger.error("Secret not found", secret=secret_name)
            raise
        except Exception as e:
            logger.error("Failed to get secret", secret=secret_name, error=str(e))
            raise


async def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    session = get_session()
    config = get_boto_config()

    async with session.client("ssm", **config) as client:
        try:
            response = await client.get_parameter(Name=name, WithDecryption=with_decryption)
            return response["Parameter"]["Value"]
        except client.exceptions.ParameterNotFound:
            logger.error("SSM parameter not found", parameter=name)
            raise
        except Exception as e:
            logger.error("Failed to get SSM parameter", parameter=name, error=str(e))
            raise


async def get_ssm_parameters_by_path(
    path: str, with_decryption: bool = True
) -> dict[str, str]:
    session = get_session()
    config = get_boto_config()
    parameters: dict[str, str] = {}

    async with session.client("ssm", **config) as client:
        try:
            paginator = client.get_paginator("get_parameters_by_path")
            async for page in paginator.paginate(
                Path=path, WithDecryption=with_decryption, Recursive=True
            ):
                for param in page.get("Parameters", []):
                    key = param["Name"].replace(path, "").lstrip("/")
                    parameters[key] = param["Value"]
            return parameters
        except Exception as e:
            logger.error("Failed to get SSM parameters by path", path=path, error=str(e))
            raise


async def encrypt_with_kms(key_id: str, plaintext: bytes) -> bytes:
    session = get_session()
    config = get_boto_config()

    async with session.client("kms", **config) as client:
        try:
            response = await client.encrypt(KeyId=key_id, Plaintext=plaintext)
            return response["CiphertextBlob"]
        except Exception as e:
            logger.error("KMS encryption failed", key_id=key_id, error=str(e))
            raise


async def decrypt_with_kms(ciphertext: bytes) -> bytes:
    session = get_session()
    config = get_boto_config()

    async with session.client("kms", **config) as client:
        try:
            response = await client.decrypt(CiphertextBlob=ciphertext)
            return response["Plaintext"]
        except Exception as e:
            logger.error("KMS decryption failed", error=str(e))
            raise
