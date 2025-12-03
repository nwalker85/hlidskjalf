"""OpenFGA authorization module."""

from app.authz.client import (
    check_permission,
    write_relationship,
    delete_relationship,
    list_objects,
    get_openfga_client,
)

__all__ = [
    "check_permission",
    "write_relationship",
    "delete_relationship",
    "list_objects",
    "get_openfga_client",
]
