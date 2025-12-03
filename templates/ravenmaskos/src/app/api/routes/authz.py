"""Authorization API routes for OpenFGA operations."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import RequireAuth, RequireTenant
from app.authz.client import (
    batch_write_relationships,
    check_permission,
    delete_relationship,
    list_objects,
    write_relationship,
)
from app.core.logging import get_logger
from app.schemas.authz import (
    BatchWriteRequest,
    BatchWriteResponse,
    CheckPermissionRequest,
    CheckPermissionResponse,
    DeleteRelationshipRequest,
    DeleteRelationshipResponse,
    ListObjectsRequest,
    ListObjectsResponse,
    UserRolesResponse,
    WriteRelationshipRequest,
    WriteRelationshipResponse,
)

router = APIRouter(prefix="/authz", tags=["authorization"])
logger = get_logger(__name__)


@router.post("/check", response_model=CheckPermissionResponse)
async def check(
    request: CheckPermissionRequest,
    user: RequireAuth,
    tenant: RequireTenant,
) -> CheckPermissionResponse:
    """Check if a user has a specific permission on an object.

    This endpoint checks the OpenFGA authorization model to determine
    if the specified user has the given relation to the object.

    Only admins can check permissions for other users. Regular users
    can only check their own permissions.
    """
    # Only admins can check permissions for other users
    if request.user_id != user.user_id and "admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot check permissions for other users",
        )

    allowed = await check_permission(
        user_id=request.user_id,
        relation=request.relation,
        object_type=request.object_type,
        object_id=request.object_id,
    )

    return CheckPermissionResponse(
        allowed=allowed,
        user_id=request.user_id,
        relation=request.relation,
        object=f"{request.object_type}:{request.object_id}",
    )


@router.post("/objects", response_model=ListObjectsResponse)
async def list_user_objects(
    request: ListObjectsRequest,
    user: RequireAuth,
    tenant: RequireTenant,
) -> ListObjectsResponse:
    """List all objects a user has a specific relation to.

    Returns a list of object IDs that the user has the specified
    relation to. Useful for filtering lists based on permissions.

    Only admins can list objects for other users.
    """
    # Only admins can list objects for other users
    if request.user_id != user.user_id and "admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot list objects for other users",
        )

    objects = await list_objects(
        user_id=request.user_id,
        relation=request.relation,
        object_type=request.object_type,
    )

    return ListObjectsResponse(
        objects=objects,
        user_id=request.user_id,
        relation=request.relation,
        object_type=request.object_type,
    )


@router.post("/tuples", response_model=WriteRelationshipResponse)
async def write_tuple(
    request: WriteRelationshipRequest,
    user: RequireAuth,
    tenant: RequireTenant,
) -> WriteRelationshipResponse:
    """Write a relationship tuple to grant a permission.

    Creates a new relationship in the authorization model. Only admins
    can modify relationships.

    Example: Grant user "alice" the "member" relation on "organization:acme"
    """
    # Only admins can write relationships
    if "admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can modify permissions",
        )

    # Verify the object belongs to the tenant
    if request.object_type == "organization" and request.object_id != tenant.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify permissions for other organizations",
        )

    success = await write_relationship(
        user_id=request.user_id,
        relation=request.relation,
        object_type=request.object_type,
        object_id=request.object_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write relationship",
        )

    tuple_str = f"user:{request.user_id} {request.relation} {request.object_type}:{request.object_id}"
    logger.info(
        "Relationship written",
        actor=user.user_id,
        tuple=tuple_str,
    )

    return WriteRelationshipResponse(success=True, tuple=tuple_str)


@router.delete("/tuples", response_model=DeleteRelationshipResponse)
async def delete_tuple(
    request: DeleteRelationshipRequest,
    user: RequireAuth,
    tenant: RequireTenant,
) -> DeleteRelationshipResponse:
    """Delete a relationship tuple to revoke a permission.

    Removes a relationship from the authorization model. Only admins
    can modify relationships.

    Note: Deleting an "admin" relation for the last admin is allowed
    but should be handled with care by the application logic.
    """
    # Only admins can delete relationships
    if "admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can modify permissions",
        )

    # Verify the object belongs to the tenant
    if request.object_type == "organization" and request.object_id != tenant.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify permissions for other organizations",
        )

    success = await delete_relationship(
        user_id=request.user_id,
        relation=request.relation,
        object_type=request.object_type,
        object_id=request.object_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete relationship",
        )

    tuple_str = f"user:{request.user_id} {request.relation} {request.object_type}:{request.object_id}"
    logger.info(
        "Relationship deleted",
        actor=user.user_id,
        tuple=tuple_str,
    )

    return DeleteRelationshipResponse(success=True, tuple=tuple_str)


@router.post("/tuples/batch", response_model=BatchWriteResponse)
async def batch_write(
    request: BatchWriteRequest,
    user: RequireAuth,
    tenant: RequireTenant,
) -> BatchWriteResponse:
    """Write multiple relationship tuples in a single operation.

    Batch writes are atomic - either all succeed or none do.
    Maximum 100 tuples per request.
    """
    # Only admins can write relationships
    if "admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can modify permissions",
        )

    # Verify all tuples belong to the tenant
    for t in request.tuples:
        if t.object_type == "organization" and t.object_id != tenant.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify permissions for other organizations",
            )

    tuples = [
        {
            "user_id": t.user_id,
            "relation": t.relation,
            "object_type": t.object_type,
            "object_id": t.object_id,
        }
        for t in request.tuples
    ]

    success = await batch_write_relationships(tuples)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write relationships",
        )

    logger.info(
        "Batch relationships written",
        actor=user.user_id,
        count=len(tuples),
    )

    return BatchWriteResponse(success=True, count=len(tuples))


@router.get("/roles/{org_id}", response_model=UserRolesResponse)
async def get_user_roles(
    org_id: str,
    user: RequireAuth,
    tenant: RequireTenant,
) -> UserRolesResponse:
    """Get current user's roles in an organization.

    Returns whether the user is an admin, member, or viewer
    in the specified organization.
    """
    # Users can only check their own roles or admins can check anyone
    if org_id != tenant.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot check roles for other organizations",
        )

    # Check each role level
    is_admin = await check_permission(
        user_id=user.user_id,
        relation="admin",
        object_type="organization",
        object_id=org_id,
    )
    is_member = await check_permission(
        user_id=user.user_id,
        relation="member",
        object_type="organization",
        object_id=org_id,
    )
    is_viewer = await check_permission(
        user_id=user.user_id,
        relation="viewer",
        object_type="organization",
        object_id=org_id,
    )

    roles = []
    if is_admin:
        roles.append("admin")
    if is_member:
        roles.append("member")
    if is_viewer:
        roles.append("viewer")

    return UserRolesResponse(
        user_id=user.user_id,
        org_id=org_id,
        roles=roles,
        is_admin=is_admin,
        is_member=is_member,
        is_viewer=is_viewer,
    )


@router.get("/my-roles", response_model=UserRolesResponse)
async def get_my_roles(
    user: RequireAuth,
    tenant: RequireTenant,
) -> UserRolesResponse:
    """Get current user's roles in their current organization.

    Convenience endpoint that uses the tenant context to determine
    the organization.
    """
    return await get_user_roles(tenant.org_id, user, tenant)
