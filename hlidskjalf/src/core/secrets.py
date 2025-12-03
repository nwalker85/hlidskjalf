"""
Ravenhelm Secrets Client

AWS Secrets Manager client that works with both LocalStack (dev) and real AWS (prod).
Provides a unified interface for retrieving secrets with caching and lazy loading.

Usage:
    from hlidskjalf.src.core.secrets import get_secrets_client, get_secret
    
    # Get a single secret
    api_key = get_secret("ravenhelm/dev/anthropic_api_key")
    
    # Get a JSON secret and parse it
    creds = get_secret_json("ravenhelm/dev/postgres/credentials")
    password = creds["password"]
    
    # Get the client directly
    client = get_secrets_client()
    secrets = client.list_secrets()
"""

import json
import logging
import os
from functools import lru_cache
from typing import Any, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class SecretsClient:
    """
    AWS Secrets Manager client with LocalStack support.
    
    In development (LocalStack):
        - endpoint_url = http://localstack:4566
        - Uses dummy credentials (test/test)
        
    In production (AWS):
        - endpoint_url = None (uses real AWS)
        - Uses IAM role or env credentials
    """
    
    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        """
        Initialize the Secrets Manager client.
        
        Args:
            endpoint_url: LocalStack endpoint (http://localstack:4566) or None for AWS
            region_name: AWS region
            aws_access_key_id: AWS access key (optional, uses env vars if not provided)
            aws_secret_access_key: AWS secret key (optional, uses env vars if not provided)
        """
        # Auto-detect LocalStack if not specified
        if endpoint_url is None:
            endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
            if endpoint_url is None and os.environ.get("ENVIRONMENT", "development") == "development":
                # Default to LocalStack in development
                endpoint_url = "http://localstack:4566"
        
        # For LocalStack, use dummy credentials if not provided
        if endpoint_url and "localstack" in endpoint_url:
            aws_access_key_id = aws_access_key_id or "test"
            aws_secret_access_key = aws_secret_access_key or "test"
        
        config = Config(
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=10,
        )
        
        self.client = boto3.client(
            "secretsmanager",
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            config=config,
        )
        
        self.endpoint_url = endpoint_url
        self._cache: dict[str, str] = {}
        
        logger.info(
            "SecretsClient initialized",
            extra={
                "endpoint": endpoint_url or "AWS",
                "region": region_name,
            },
        )
    
    def get_secret(self, secret_name: str, use_cache: bool = True) -> str:
        """
        Retrieve a secret value by name.
        
        Args:
            secret_name: The name/ID of the secret (e.g., "ravenhelm/dev/anthropic_api_key")
            use_cache: Whether to use cached values (default: True)
            
        Returns:
            The secret string value
            
        Raises:
            SecretNotFoundError: If the secret doesn't exist
            SecretsClientError: For other errors
        """
        if use_cache and secret_name in self._cache:
            logger.debug(f"Cache hit for secret: {secret_name}")
            return self._cache[secret_name]
        
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            secret_value = response["SecretString"]
            
            if use_cache:
                self._cache[secret_name] = secret_value
            
            logger.debug(f"Retrieved secret: {secret_name}")
            return secret_value
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            
            if error_code == "ResourceNotFoundException":
                logger.error(f"Secret not found: {secret_name}")
                raise SecretNotFoundError(f"Secret '{secret_name}' not found") from e
            elif error_code == "AccessDeniedException":
                logger.error(f"Access denied to secret: {secret_name}")
                raise SecretsClientError(f"Access denied to secret '{secret_name}'") from e
            else:
                logger.error(f"Error retrieving secret {secret_name}: {e}")
                raise SecretsClientError(f"Error retrieving secret: {e}") from e
    
    def get_secret_json(self, secret_name: str, use_cache: bool = True) -> dict[str, Any]:
        """
        Retrieve a secret and parse it as JSON.
        
        Args:
            secret_name: The name/ID of the secret
            use_cache: Whether to use cached values
            
        Returns:
            The secret parsed as a dictionary
        """
        secret_value = self.get_secret(secret_name, use_cache=use_cache)
        try:
            return json.loads(secret_value)
        except json.JSONDecodeError as e:
            logger.error(f"Secret {secret_name} is not valid JSON: {e}")
            raise SecretsClientError(f"Secret '{secret_name}' is not valid JSON") from e
    
    def list_secrets(self, prefix: Optional[str] = None) -> list[str]:
        """
        List all secret names, optionally filtered by prefix.
        
        Args:
            prefix: Optional prefix to filter secrets (e.g., "ravenhelm/dev/")
            
        Returns:
            List of secret names
        """
        try:
            paginator = self.client.get_paginator("list_secrets")
            secret_names = []
            
            for page in paginator.paginate():
                for secret in page.get("SecretList", []):
                    name = secret.get("Name", "")
                    if prefix is None or name.startswith(prefix):
                        secret_names.append(name)
            
            return sorted(secret_names)
            
        except ClientError as e:
            logger.error(f"Error listing secrets: {e}")
            raise SecretsClientError(f"Error listing secrets: {e}") from e
    
    def secret_exists(self, secret_name: str) -> bool:
        """Check if a secret exists."""
        try:
            self.client.describe_secret(SecretId=secret_name)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                return False
            raise SecretsClientError(f"Error checking secret existence: {e}") from e
    
    def clear_cache(self, secret_name: Optional[str] = None) -> None:
        """
        Clear the secret cache.
        
        Args:
            secret_name: If provided, only clear this secret. Otherwise clear all.
        """
        if secret_name:
            self._cache.pop(secret_name, None)
            logger.debug(f"Cleared cache for secret: {secret_name}")
        else:
            self._cache.clear()
            logger.debug("Cleared entire secrets cache")
    
    def create_secret(
        self,
        secret_name: str,
        secret_value: str,
        description: Optional[str] = None,
    ) -> str:
        """
        Create a new secret (useful for testing/development).
        
        Args:
            secret_name: The name for the secret
            secret_value: The secret value
            description: Optional description
            
        Returns:
            The ARN of the created secret
        """
        try:
            kwargs = {
                "Name": secret_name,
                "SecretString": secret_value,
            }
            if description:
                kwargs["Description"] = description
            
            response = self.client.create_secret(**kwargs)
            logger.info(f"Created secret: {secret_name}")
            return response["ARN"]
            
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceExistsException":
                logger.warning(f"Secret already exists: {secret_name}")
                # Update instead
                self.client.put_secret_value(
                    SecretId=secret_name,
                    SecretString=secret_value,
                )
                return secret_name
            raise SecretsClientError(f"Error creating secret: {e}") from e


class SecretsClientError(Exception):
    """Base exception for secrets client errors."""
    pass


class SecretNotFoundError(SecretsClientError):
    """Raised when a secret is not found."""
    pass


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

_secrets_client: Optional[SecretsClient] = None


def get_secrets_client() -> SecretsClient:
    """
    Get a cached SecretsClient instance.
    
    Returns:
        The singleton SecretsClient instance
    """
    global _secrets_client
    if _secrets_client is None:
        _secrets_client = SecretsClient()
    return _secrets_client


def get_secret(secret_name: str, use_cache: bool = True) -> str:
    """
    Convenience function to get a secret value.
    
    Args:
        secret_name: The name/ID of the secret
        use_cache: Whether to use cached values
        
    Returns:
        The secret string value
    """
    return get_secrets_client().get_secret(secret_name, use_cache=use_cache)


def get_secret_json(secret_name: str, use_cache: bool = True) -> dict[str, Any]:
    """
    Convenience function to get a secret as JSON.
    
    Args:
        secret_name: The name/ID of the secret
        use_cache: Whether to use cached values
        
    Returns:
        The secret parsed as a dictionary
    """
    return get_secrets_client().get_secret_json(secret_name, use_cache=use_cache)


@lru_cache(maxsize=100)
def get_secret_cached(secret_name: str) -> str:
    """
    Get a secret with function-level caching (for use outside class instances).
    
    This uses functools.lru_cache for permanent caching within the process lifetime.
    Use this for secrets that never change during runtime.
    
    Args:
        secret_name: The name/ID of the secret
        
    Returns:
        The secret string value
    """
    return get_secrets_client().get_secret(secret_name, use_cache=False)

