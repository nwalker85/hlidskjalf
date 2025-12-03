"""OpenFGA client wrapper for authorization operations."""

import json
from pathlib import Path
from typing import Any

from openfga_sdk import ClientConfiguration, OpenFgaClient
from openfga_sdk.client.models import (
    ClientCheckRequest,
    ClientListObjectsRequest,
    ClientTuple,
    ClientWriteRequest,
)
from openfga_sdk.models import CreateStoreRequest, WriteAuthorizationModelRequest

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global client instance
_client: OpenFgaClient | None = None
_store_id: str | None = None
_model_id: str | None = None


async def get_openfga_client() -> OpenFgaClient:
    """Get or create OpenFGA client instance."""
    global _client
    if _client is None:
        configuration = ClientConfiguration(
            api_url=settings.OPENFGA_API_URL,
        )
        _client = OpenFgaClient(configuration)
    return _client


async def ensure_store_and_model() -> tuple[str, str]:
    """Ensure OpenFGA store and authorization model exist.

    Returns:
        Tuple of (store_id, model_id)
    """
    global _store_id, _model_id

    if _store_id and _model_id:
        return _store_id, _model_id

    client = await get_openfga_client()

    # Check for existing store
    stores = await client.list_stores()
    store = next(
        (s for s in (stores.stores or []) if s.name == settings.OPENFGA_STORE_NAME),
        None,
    )

    if store:
        _store_id = store.id
        logger.info("Using existing OpenFGA store", store_id=_store_id)
    else:
        # Create new store
        response = await client.create_store(
            CreateStoreRequest(name=settings.OPENFGA_STORE_NAME)
        )
        _store_id = response.id
        logger.info("Created new OpenFGA store", store_id=_store_id)

    # Set store ID on client configuration
    client.set_store_id(_store_id)

    # Check for existing model
    models = await client.read_authorization_models()
    if models.authorization_models:
        _model_id = models.authorization_models[0].id
        logger.info("Using existing authorization model", model_id=_model_id)
    else:
        # Load and create model from FGA file
        model_path = Path(__file__).parent / "model.json"
        if not model_path.exists():
            raise RuntimeError(
                "Authorization model not found. Run 'fga model transform' to generate model.json"
            )

        with open(model_path) as f:
            model_data = json.load(f)

        response = await client.write_authorization_model(
            WriteAuthorizationModelRequest(**model_data)
        )
        _model_id = response.authorization_model_id
        logger.info("Created authorization model", model_id=_model_id)

    client.set_authorization_model_id(_model_id)
    return _store_id, _model_id


async def check_permission(
    user_id: str,
    relation: str,
    object_type: str,
    object_id: str,
) -> bool:
    """Check if user has permission on an object.

    Args:
        user_id: The user ID (will be formatted as "user:{user_id}")
        relation: The relation to check (e.g., "admin", "member", "viewer")
        object_type: The object type (e.g., "organization", "api_key")
        object_id: The object ID

    Returns:
        True if user has the permission, False otherwise
    """
    client = await get_openfga_client()
    await ensure_store_and_model()

    try:
        response = await client.check(
            ClientCheckRequest(
                user=f"user:{user_id}",
                relation=relation,
                object=f"{object_type}:{object_id}",
            )
        )
        return response.allowed or False
    except Exception as e:
        logger.error(
            "Permission check failed",
            user_id=user_id,
            relation=relation,
            object=f"{object_type}:{object_id}",
            error=str(e),
        )
        return False


async def write_relationship(
    user_id: str,
    relation: str,
    object_type: str,
    object_id: str,
) -> bool:
    """Write a relationship tuple.

    Args:
        user_id: The user ID
        relation: The relation (e.g., "admin", "member")
        object_type: The object type (e.g., "organization")
        object_id: The object ID

    Returns:
        True if successful, False otherwise
    """
    client = await get_openfga_client()
    await ensure_store_and_model()

    try:
        await client.write(
            ClientWriteRequest(
                writes=[
                    ClientTuple(
                        user=f"user:{user_id}",
                        relation=relation,
                        object=f"{object_type}:{object_id}",
                    )
                ]
            )
        )
        logger.info(
            "Relationship written",
            user_id=user_id,
            relation=relation,
            object=f"{object_type}:{object_id}",
        )
        return True
    except Exception as e:
        logger.error(
            "Failed to write relationship",
            user_id=user_id,
            relation=relation,
            object=f"{object_type}:{object_id}",
            error=str(e),
        )
        return False


async def delete_relationship(
    user_id: str,
    relation: str,
    object_type: str,
    object_id: str,
) -> bool:
    """Delete a relationship tuple.

    Args:
        user_id: The user ID
        relation: The relation to remove
        object_type: The object type
        object_id: The object ID

    Returns:
        True if successful, False otherwise
    """
    client = await get_openfga_client()
    await ensure_store_and_model()

    try:
        await client.write(
            ClientWriteRequest(
                deletes=[
                    ClientTuple(
                        user=f"user:{user_id}",
                        relation=relation,
                        object=f"{object_type}:{object_id}",
                    )
                ]
            )
        )
        logger.info(
            "Relationship deleted",
            user_id=user_id,
            relation=relation,
            object=f"{object_type}:{object_id}",
        )
        return True
    except Exception as e:
        logger.error(
            "Failed to delete relationship",
            user_id=user_id,
            relation=relation,
            object=f"{object_type}:{object_id}",
            error=str(e),
        )
        return False


async def list_objects(
    user_id: str,
    relation: str,
    object_type: str,
) -> list[str]:
    """List all objects a user has a specific relation to.

    Args:
        user_id: The user ID
        relation: The relation to check (e.g., "member")
        object_type: The object type to list (e.g., "organization")

    Returns:
        List of object IDs the user has the relation to
    """
    client = await get_openfga_client()
    await ensure_store_and_model()

    try:
        response = await client.list_objects(
            ClientListObjectsRequest(
                user=f"user:{user_id}",
                relation=relation,
                type=object_type,
            )
        )
        # Extract IDs from "type:id" format
        objects = response.objects or []
        return [obj.split(":", 1)[1] if ":" in obj else obj for obj in objects]
    except Exception as e:
        logger.error(
            "Failed to list objects",
            user_id=user_id,
            relation=relation,
            object_type=object_type,
            error=str(e),
        )
        return []


async def batch_write_relationships(
    tuples: list[dict[str, str]],
) -> bool:
    """Write multiple relationship tuples at once.

    Args:
        tuples: List of dicts with keys: user_id, relation, object_type, object_id

    Returns:
        True if all successful, False otherwise
    """
    client = await get_openfga_client()
    await ensure_store_and_model()

    try:
        writes = [
            ClientTuple(
                user=f"user:{t['user_id']}",
                relation=t["relation"],
                object=f"{t['object_type']}:{t['object_id']}",
            )
            for t in tuples
        ]
        await client.write(ClientWriteRequest(writes=writes))
        logger.info("Batch relationships written", count=len(tuples))
        return True
    except Exception as e:
        logger.error("Failed to batch write relationships", error=str(e))
        return False


async def close_client() -> None:
    """Close the OpenFGA client connection."""
    global _client, _store_id, _model_id
    if _client:
        await _client.close()
        _client = None
        _store_id = None
        _model_id = None
