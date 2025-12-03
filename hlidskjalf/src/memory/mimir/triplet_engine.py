"""
Mímir Triplet Engine - Resolve valid actions from domain knowledge

Evaluates AgenticTriplets against AccessGates with JMESPath conditions.
"""

from __future__ import annotations

import logging
from typing import Any

from src.memory.mimir.models import (
    DISDossier,
    AgenticTriplet,
    AccessGate,
    ModeOfInteraction,
)

logger = logging.getLogger(__name__)


class MimirTripletEngine:
    """
    Resolve valid AgenticTriplets for a given context.
    
    The engine:
    1. Finds triplets for a role
    2. Checks AccessGates (RBAC)
    3. Evaluates JMESPath conditions against context
    4. Returns only valid triplets
    """
    
    def __init__(self, dossier: DISDossier):
        self.dossier = dossier
        
        # Index access gates by (role_id, entity_id)
        self._access_gates: dict[tuple[str, str], AccessGate] = {}
        for gate in dossier.accessGates:
            key = (gate.roleId, gate.entityId)
            # Use highest priority if multiple gates
            if key not in self._access_gates or gate.priority > self._access_gates[key].priority:
                self._access_gates[key] = gate
        
        # Index triplets by role
        self._triplets_by_role: dict[str, list[AgenticTriplet]] = {}
        for triplet in dossier.triplets:
            role = triplet.actingRoleId
            if role not in self._triplets_by_role:
                self._triplets_by_role[role] = []
            self._triplets_by_role[role].append(triplet)
    
    def consult(
        self,
        role_id: str,
        context: dict[str, Any] | None = None,
    ) -> list[AgenticTriplet]:
        """
        What may this role do, given the context?
        
        Returns valid triplets for the role that pass access gate checks.
        """
        context = context or {}
        
        # Get all triplets for this role
        role_triplets = self._triplets_by_role.get(role_id, [])
        if not role_triplets:
            logger.debug(f"No triplets found for role {role_id}")
            return []
        
        valid_triplets = []
        
        for triplet in role_triplets:
            # Check access gate
            gate = self._access_gates.get((role_id, triplet.targetEntityId))
            
            if not gate:
                # No gate = no access
                logger.debug(
                    f"No access gate for {role_id} -> {triplet.targetEntityId}"
                )
                continue
            
            # Check if mode is allowed
            if triplet.modeOfInteraction not in gate.allowedModes:
                logger.debug(
                    f"Mode {triplet.modeOfInteraction} not allowed for "
                    f"{role_id} -> {triplet.targetEntityId}"
                )
                continue
            
            # Evaluate JMESPath condition if present
            if gate.gateCondition:
                if not self._evaluate_condition(gate.gateCondition, context):
                    logger.debug(
                        f"Gate condition failed for triplet {triplet.tripletId}"
                    )
                    continue
            
            valid_triplets.append(triplet)
        
        logger.debug(
            f"Mímir consulted for role {role_id}: "
            f"{len(valid_triplets)}/{len(role_triplets)} triplets valid"
        )
        
        return valid_triplets
    
    def _evaluate_condition(self, condition: str, context: dict[str, Any]) -> bool:
        """
        Evaluate a JMESPath condition against context.
        
        Returns True if condition passes, False otherwise.
        """
        try:
            import jmespath
            result = jmespath.search(condition, context)
            return bool(result)
        except ImportError:
            logger.warning("jmespath not installed, skipping condition evaluation")
            return True
        except Exception as e:
            logger.error(f"Failed to evaluate condition '{condition}': {e}")
            return False
    
    def can_act(
        self,
        role_id: str,
        entity_id: str,
        mode: ModeOfInteraction,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """
        Check if a role can perform a specific mode on an entity.
        
        Quick check without returning the full triplet.
        """
        context = context or {}
        
        gate = self._access_gates.get((role_id, entity_id))
        if not gate:
            return False
        
        if mode not in gate.allowedModes:
            return False
        
        if gate.gateCondition:
            return self._evaluate_condition(gate.gateCondition, context)
        
        return True
    
    def get_allowed_modes(
        self,
        role_id: str,
        entity_id: str,
        context: dict[str, Any] | None = None,
    ) -> list[ModeOfInteraction]:
        """
        Get all allowed modes for a role-entity pair.
        """
        context = context or {}
        
        gate = self._access_gates.get((role_id, entity_id))
        if not gate:
            return []
        
        # If no condition, return all allowed modes
        if not gate.gateCondition:
            return list(gate.allowedModes)
        
        # If condition fails, no modes allowed
        if not self._evaluate_condition(gate.gateCondition, context):
            return []
        
        return list(gate.allowedModes)
    
    def get_triplet_by_id(self, triplet_id: str) -> AgenticTriplet | None:
        """Get a specific triplet by ID"""
        return self.dossier.get_triplet(triplet_id)
    
    def get_triplets_for_entity(self, entity_id: str) -> list[AgenticTriplet]:
        """Get all triplets targeting an entity"""
        return [
            t for t in self.dossier.triplets
            if t.targetEntityId == entity_id
        ]
    
    def get_triplets_by_mode(
        self,
        mode: ModeOfInteraction,
    ) -> list[AgenticTriplet]:
        """Get all triplets with a specific mode"""
        return [
            t for t in self.dossier.triplets
            if t.modeOfInteraction == mode
        ]
    
    def explain_denial(
        self,
        role_id: str,
        entity_id: str,
        mode: ModeOfInteraction,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Explain why a particular action is denied.
        
        Useful for debugging and user feedback.
        """
        context = context or {}
        
        gate = self._access_gates.get((role_id, entity_id))
        
        if not gate:
            return f"No access gate defined for role '{role_id}' on entity '{entity_id}'"
        
        if mode not in gate.allowedModes:
            allowed = ", ".join(m.value for m in gate.allowedModes)
            return (
                f"Mode '{mode.value}' not allowed for role '{role_id}' "
                f"on entity '{entity_id}'. Allowed modes: {allowed}"
            )
        
        if gate.gateCondition:
            if not self._evaluate_condition(gate.gateCondition, context):
                return (
                    f"Gate condition not satisfied: {gate.gateCondition}. "
                    f"Context: {context}"
                )
        
        return "Action is allowed"
    
    def generate_candidate_triplets(
        self,
        role_id: str,
        entity_id: str,
    ) -> list[AgenticTriplet]:
        """
        Generate candidate triplets for a role-entity pair.
        
        Creates triplets for all allowed modes (before context check).
        Useful for documentation and analysis.
        """
        gate = self._access_gates.get((role_id, entity_id))
        if not gate:
            return []
        
        candidates = []
        for mode in gate.allowedModes:
            triplet = AgenticTriplet(
                tripletId=f"tri-{role_id}-{mode.value.lower()}-{entity_id}",
                name=f"{role_id} {mode.value} {entity_id}",
                actingEntityId="",  # Would need entity lookup
                actingRoleId=role_id,
                stance="ACT" if mode in [ModeOfInteraction.CREATE, ModeOfInteraction.UPDATE, ModeOfInteraction.DELETE, ModeOfInteraction.INITIATE, ModeOfInteraction.NOTIFY] else "REACT",
                modeOfInteraction=mode,
                targetEntityId=entity_id,
            )
            candidates.append(triplet)
        
        return candidates

