"""
DIS 1.6 Models - Domain Intelligence Schema core constructs

Based on https://schemas.domainintelligenceschema.org/dis/1.6.0/
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ModeOfInteraction(str, Enum):
    """The 7 canonical modes of interaction"""
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    INITIATE = "INITIATE"
    RESPOND = "RESPOND"
    NOTIFY = "NOTIFY"


class Stance(str, Enum):
    """Actor stance in a triplet"""
    ACT = "ACT"      # Proactive
    REACT = "REACT"  # Reactive


class EntityType(str, Enum):
    """Types of entities"""
    DATA = "data"
    AGENT = "agent"


class RoleType(str, Enum):
    """Types of roles"""
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


class Entity(BaseModel):
    """
    DIS Entity - A data object or AI agent in the domain.
    
    Anything that needs policy, telemetry, or lifecycle must be an Entity.
    """
    entityId: str
    name: str
    entityType: EntityType
    description: str | None = None
    
    # Key structure
    primaryKey: str | None = None
    foreignKeys: dict[str, str] = Field(default_factory=dict)
    
    # Attributes
    attributes: list[dict[str, Any]] = Field(default_factory=list)
    
    # Assigned roles
    assignedRoleIds: list[str] = Field(default_factory=list)
    
    # Privacy classification
    privacyClassification: str | None = None
    
    # Tags
    appliedTags: list[str] = Field(default_factory=list)
    
    # Metadata
    version: str = "1.0.0"


class Role(BaseModel):
    """
    DIS Role - A capacity or "hat" that entities wear.
    
    Roles are not actors - they define what an entity can do.
    """
    roleId: str
    name: str
    roleType: RoleType
    description: str | None = None
    
    # Role attributes
    attributes: list[dict[str, Any]] = Field(default_factory=list)
    
    # Agent archetype (for AI roles)
    agentArchetype: str | None = None
    
    # Assigned entities
    assignedEntityIds: list[str] = Field(default_factory=list)
    
    # Tags
    appliedTags: list[str] = Field(default_factory=list)


class AgenticTriplet(BaseModel):
    """
    DIS AgenticTriplet - The atomic behavioral sentence.
    
    (actingEntity, actingRole, stance, modeOfInteraction, targetEntity)
    
    This is the core grammar of domain behavior.
    """
    tripletId: str
    name: str
    description: str | None = None
    
    # The behavioral sentence
    actingEntityId: str
    actingRoleId: str
    stance: Stance
    modeOfInteraction: ModeOfInteraction
    targetEntityId: str
    
    # Context and constraints
    contextDescription: str | None = None
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    
    # Tags
    appliedTags: list[str] = Field(default_factory=list)
    
    def to_sentence(self) -> str:
        """Convert triplet to natural language sentence"""
        return (
            f"{self.actingEntityId} (as {self.actingRoleId}) "
            f"can {self.stance.value} {self.modeOfInteraction.value} "
            f"on {self.targetEntityId}"
        )


class AccessGate(BaseModel):
    """
    DIS AccessGateMatrix Entry - RBAC rule with JMESPath condition.
    
    Specifies what modes a role can use on an entity, under what conditions.
    """
    gateId: str
    roleId: str
    entityId: str
    
    # Allowed modes
    allowedModes: list[ModeOfInteraction]
    
    # JMESPath condition that must evaluate to true
    gateCondition: str | None = None
    
    # Description
    description: str | None = None
    
    # Priority for conflict resolution
    priority: int = 0


class EntityModeEntry(BaseModel):
    """
    DIS EntityModeMatrix Entry - Capability surface for an entity.
    
    Defines what modes an entity can operate in and with what stance.
    """
    entryId: str
    entityId: str
    
    # Enabled modes
    modes: list[ModeOfInteraction]
    
    # Stance (ACT or REACT)
    stance: Stance
    
    # Description of capability
    description: str | None = None


class FunctionCatalogEntry(BaseModel):
    """
    DIS FunctionCatalogEntry - A semantic operation.
    
    Functions describe "what" the system does, not "how".
    """
    functionId: str
    name: str
    description: str | None = None
    
    # Parameters
    inputParameters: list[dict[str, Any]] = Field(default_factory=list)
    outputParameters: list[dict[str, Any]] = Field(default_factory=list)
    
    # System of record
    systemOfRecord: str | None = None


class TripletFunctionBinding(BaseModel):
    """
    DIS TripletFunctionMatrixEntry - Binds triplets to functions.
    
    Connects behavioral grammar to execution.
    """
    bindingId: str
    tripletId: str
    functionId: str
    
    # Execution details
    endpointId: str | None = None
    priority: int = 0
    contextDescription: str | None = None


class RelationshipEntry(BaseModel):
    """
    DIS RelationshipMatrix Entry - Semantic relationship between constructs.
    """
    relationshipId: str
    sourceId: str
    targetId: str
    relationshipType: str  # "owns", "tracks", "aggregates", etc.
    description: str | None = None


class DISDossier(BaseModel):
    """
    DIS Dossier - The root container for domain intelligence.
    
    A complete, compiled domain-specific package.
    """
    dossierId: str
    name: str
    version: str = "1.0.0"
    disSpecificationRef: str = "1.6.0"
    description: str | None = None
    
    # Domain scope
    domainName: str | None = None
    
    # Core constructs
    entities: list[Entity] = Field(default_factory=list)
    roles: list[Role] = Field(default_factory=list)
    triplets: list[AgenticTriplet] = Field(default_factory=list)
    
    # Matrices
    accessGates: list[AccessGate] = Field(default_factory=list)
    entityModes: list[EntityModeEntry] = Field(default_factory=list)
    relationships: list[RelationshipEntry] = Field(default_factory=list)
    
    # Execution
    functions: list[FunctionCatalogEntry] = Field(default_factory=list)
    tripletBindings: list[TripletFunctionBinding] = Field(default_factory=list)
    
    # Metadata
    createdAt: datetime | None = None
    updatedAt: datetime | None = None
    
    def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID"""
        return next((e for e in self.entities if e.entityId == entity_id), None)
    
    def get_role(self, role_id: str) -> Role | None:
        """Get role by ID"""
        return next((r for r in self.roles if r.roleId == role_id), None)
    
    def get_triplet(self, triplet_id: str) -> AgenticTriplet | None:
        """Get triplet by ID"""
        return next((t for t in self.triplets if t.tripletId == triplet_id), None)
    
    def get_triplets_for_role(self, role_id: str) -> list[AgenticTriplet]:
        """Get all triplets where the role is acting"""
        return [t for t in self.triplets if t.actingRoleId == role_id]
    
    def get_access_gate(self, role_id: str, entity_id: str) -> AccessGate | None:
        """Get access gate for role-entity pair"""
        return next(
            (g for g in self.accessGates 
             if g.roleId == role_id and g.entityId == entity_id),
            None
        )

