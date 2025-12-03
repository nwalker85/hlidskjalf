"""Authorization request/response schemas for OpenFGA."""

from pydantic import BaseModel, Field


class CheckPermissionRequest(BaseModel):
    """Request to check if a user has a permission on an object."""

    user_id: str = Field(..., description="User ID to check permission for")
    relation: str = Field(..., description="Relation to check (e.g., 'admin', 'member', 'can_view')")
    object_type: str = Field(..., description="Object type (e.g., 'organization', 'project')")
    object_id: str = Field(..., description="Object ID to check permission on")


class CheckPermissionResponse(BaseModel):
    """Response from permission check."""

    allowed: bool
    user_id: str
    relation: str
    object: str = Field(description="Object in 'type:id' format")


class ListObjectsRequest(BaseModel):
    """Request to list objects a user has access to."""

    user_id: str = Field(..., description="User ID to list objects for")
    relation: str = Field(..., description="Relation to filter by (e.g., 'member', 'viewer')")
    object_type: str = Field(..., description="Object type to list (e.g., 'organization')")


class ListObjectsResponse(BaseModel):
    """Response containing list of accessible object IDs."""

    objects: list[str] = Field(default_factory=list, description="List of object IDs")
    user_id: str
    relation: str
    object_type: str


class RelationshipTuple(BaseModel):
    """A relationship tuple to write or delete."""

    user_id: str = Field(..., description="User ID")
    relation: str = Field(..., description="Relation (e.g., 'admin', 'member')")
    object_type: str = Field(..., description="Object type (e.g., 'organization')")
    object_id: str = Field(..., description="Object ID")


class WriteRelationshipRequest(BaseModel):
    """Request to write a relationship tuple."""

    user_id: str = Field(..., description="User ID to grant permission to")
    relation: str = Field(..., description="Relation to grant")
    object_type: str = Field(..., description="Object type")
    object_id: str = Field(..., description="Object ID")


class WriteRelationshipResponse(BaseModel):
    """Response after writing relationship."""

    success: bool
    tuple: str = Field(description="Tuple in 'user:X relation object:Y' format")


class DeleteRelationshipRequest(BaseModel):
    """Request to delete a relationship tuple."""

    user_id: str = Field(..., description="User ID to revoke permission from")
    relation: str = Field(..., description="Relation to revoke")
    object_type: str = Field(..., description="Object type")
    object_id: str = Field(..., description="Object ID")


class DeleteRelationshipResponse(BaseModel):
    """Response after deleting relationship."""

    success: bool
    tuple: str = Field(description="Deleted tuple in 'user:X relation object:Y' format")


class BatchWriteRequest(BaseModel):
    """Request to write multiple relationship tuples."""

    tuples: list[RelationshipTuple] = Field(..., min_length=1, max_length=100)


class BatchWriteResponse(BaseModel):
    """Response after batch writing relationships."""

    success: bool
    count: int = Field(description="Number of tuples written")


class UserRolesResponse(BaseModel):
    """Response containing user's roles in an organization."""

    user_id: str
    org_id: str
    roles: list[str] = Field(description="List of roles (admin, member, viewer)")
    is_admin: bool
    is_member: bool
    is_viewer: bool
