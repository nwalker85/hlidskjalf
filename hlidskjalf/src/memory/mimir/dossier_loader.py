"""
Mímir Dossier Loader - Load and validate DIS 1.6 dossiers

Loads domain intelligence from Git-backed JSON files.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.memory.mimir.models import (
    DISDossier,
    Entity,
    Role,
    AgenticTriplet,
    AccessGate,
    EntityModeEntry,
    FunctionCatalogEntry,
    RelationshipEntry,
)

logger = logging.getLogger(__name__)


class MimirDossierLoader:
    """
    Mímir guards the Well of Wisdom (DIS 1.6 Dossiers).
    
    Loads and validates domain intelligence from dossier files.
    """
    
    SCHEMA_BASE = "https://schemas.domainintelligenceschema.org/dis/1.6.0/"
    
    def __init__(self, dossier_path: Path | str):
        self.dossier_path = Path(dossier_path)
        self._dossier: DISDossier | None = None
        self._raw: dict[str, Any] | None = None
    
    def load_wisdom(self) -> DISDossier:
        """
        Load the domain's truth.
        
        Loads from dossier.json or constructs from individual files.
        """
        if self._dossier:
            return self._dossier
        
        dossier_file = self.dossier_path / "dossier.json"
        
        if dossier_file.exists():
            # Load monolithic dossier
            self._dossier = self._load_from_file(dossier_file)
        else:
            # Load from component files
            self._dossier = self._load_from_components()
        
        logger.info(f"Mímir loaded dossier: {self._dossier.name}")
        return self._dossier
    
    def _load_from_file(self, path: Path) -> DISDossier:
        """Load dossier from a single JSON file"""
        logger.debug(f"Loading dossier from {path}")
        
        with open(path) as f:
            data = json.load(f)
        
        self._raw = data
        return DISDossier.model_validate(data)
    
    def _load_from_components(self) -> DISDossier:
        """Load dossier from component directories"""
        logger.debug(f"Loading dossier from components in {self.dossier_path}")
        
        # Load entities
        entities = self._load_directory(
            self.dossier_path / "entities",
            Entity,
        )
        
        # Load roles
        roles = self._load_directory(
            self.dossier_path / "roles",
            Role,
        )
        
        # Load triplets
        triplets = self._load_directory(
            self.dossier_path / "triplets",
            AgenticTriplet,
        )
        
        # Load access gates
        access_gates = self._load_directory(
            self.dossier_path / "access_gates",
            AccessGate,
        )
        
        # Load functions
        functions = self._load_directory(
            self.dossier_path / "functions",
            FunctionCatalogEntry,
        )
        
        # Construct dossier
        dossier = DISDossier(
            dossierId=self.dossier_path.name,
            name=self.dossier_path.name,
            entities=entities,
            roles=roles,
            triplets=triplets,
            accessGates=access_gates,
            functions=functions,
        )
        
        return dossier
    
    def _load_directory(self, path: Path, model_class) -> list:
        """Load all JSON files from a directory as model instances"""
        items = []
        
        if not path.exists():
            return items
        
        for file in path.glob("*.json"):
            try:
                with open(file) as f:
                    data = json.load(f)
                
                # Handle both single item and array
                if isinstance(data, list):
                    items.extend(model_class.model_validate(d) for d in data)
                else:
                    items.append(model_class.model_validate(data))
                    
            except Exception as e:
                logger.error(f"Failed to load {file}: {e}")
        
        return items
    
    def get_entities(self) -> list[Entity]:
        """Get all entity definitions"""
        dossier = self.load_wisdom()
        return dossier.entities
    
    def get_roles(self) -> list[Role]:
        """Get all role definitions"""
        dossier = self.load_wisdom()
        return dossier.roles
    
    def get_triplets(self) -> list[AgenticTriplet]:
        """Get all AgenticTriplets"""
        dossier = self.load_wisdom()
        return dossier.triplets
    
    def get_access_gates(self) -> list[AccessGate]:
        """Get RBAC rules"""
        dossier = self.load_wisdom()
        return dossier.accessGates
    
    def get_entity(self, entity_id: str) -> Entity | None:
        """Get a specific entity"""
        dossier = self.load_wisdom()
        return dossier.get_entity(entity_id)
    
    def get_role(self, role_id: str) -> Role | None:
        """Get a specific role"""
        dossier = self.load_wisdom()
        return dossier.get_role(role_id)
    
    def validate(self) -> list[str]:
        """
        Validate dossier referential integrity.
        
        Returns list of validation errors.
        """
        errors = []
        dossier = self.load_wisdom()
        
        entity_ids = {e.entityId for e in dossier.entities}
        role_ids = {r.roleId for r in dossier.roles}
        
        # Validate triplet references
        for triplet in dossier.triplets:
            if triplet.actingEntityId not in entity_ids:
                errors.append(
                    f"Triplet {triplet.tripletId} references unknown entity: "
                    f"{triplet.actingEntityId}"
                )
            if triplet.targetEntityId not in entity_ids:
                errors.append(
                    f"Triplet {triplet.tripletId} references unknown entity: "
                    f"{triplet.targetEntityId}"
                )
            if triplet.actingRoleId not in role_ids:
                errors.append(
                    f"Triplet {triplet.tripletId} references unknown role: "
                    f"{triplet.actingRoleId}"
                )
        
        # Validate access gate references
        for gate in dossier.accessGates:
            if gate.entityId not in entity_ids:
                errors.append(
                    f"AccessGate {gate.gateId} references unknown entity: "
                    f"{gate.entityId}"
                )
            if gate.roleId not in role_ids:
                errors.append(
                    f"AccessGate {gate.gateId} references unknown role: "
                    f"{gate.roleId}"
                )
        
        # Validate entity role assignments
        for entity in dossier.entities:
            for role_id in entity.assignedRoleIds:
                if role_id not in role_ids:
                    errors.append(
                        f"Entity {entity.entityId} references unknown role: {role_id}"
                    )
        
        if errors:
            logger.warning(f"Dossier validation found {len(errors)} errors")
        else:
            logger.info("Dossier validation passed")
        
        return errors
    
    def reload(self) -> DISDossier:
        """Force reload of dossier"""
        self._dossier = None
        self._raw = None
        return self.load_wisdom()
    
    def to_dict(self) -> dict[str, Any]:
        """Export dossier as dictionary"""
        dossier = self.load_wisdom()
        return dossier.model_dump()

