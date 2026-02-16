"""
Linear Dispatcher - Pulls tickets from Linear and dispatches to agents

This module provides the bridge between Linear project management and
the Norns agent orchestration system.

Workflow:
1. Pull prioritized tickets from Linear (via MCP or API)
2. Filter for ready-to-work items (Todo status)
3. Match tickets to agents based on labels
4. Dispatch assignments via ticket_orchestrator
5. Update Linear when work completes
"""

import asyncio
from datetime import datetime
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field

from src.norns.ticket_orchestrator import (
    TicketOrchestrator,
    LinearTicket,
    TicketPriority,
    ClaudeAgentRole,
    Whiteboard,
    LABEL_TO_AGENT,
    AUTONOMOUS_ROLES,
)


class LinearState(str, Enum):
    """Linear issue states"""
    BACKLOG = "Backlog"
    TODO = "Todo"
    IN_PROGRESS = "In Progress"
    IN_REVIEW = "In Review"
    DONE = "Done"
    CANCELLED = "Cancelled"


class SprintPlan(BaseModel):
    """A sprint plan with selected tickets"""
    sprint_name: str
    sprint_goal: str
    tickets: list[LinearTicket]
    total_estimate_hours: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class LinearDispatcher:
    """
    Dispatcher that pulls from Linear and assigns to agents.

    This is the "product lead" side of the whiteboard system:
    - Prioritizes work
    - Creates sprint plans
    - Dispatches tickets to the orchestrator
    """

    def __init__(
        self,
        orchestrator: TicketOrchestrator,
        team_id: str = "3f8d849b-c1f6-4be8-b2fe-b65246fe3876",  # Ravenhelm
    ):
        self.orchestrator = orchestrator
        self.team_id = team_id
        self.whiteboard = Whiteboard(orchestrator)

        # Sprint planning state
        self.current_sprint: Optional[SprintPlan] = None
        self.backlog: list[LinearTicket] = []

    def load_backlog(self, issues: list[dict]) -> list[LinearTicket]:
        """
        Convert Linear API response to LinearTicket objects.

        Args:
            issues: List of issues from Linear API/MCP
        """
        tickets = []

        for issue in issues:
            # Map Linear priority (1-4) to TicketPriority
            linear_priority = issue.get("priority", 0)
            priority_map = {
                1: TicketPriority.URGENT,
                2: TicketPriority.HIGH,
                3: TicketPriority.MEDIUM,
                4: TicketPriority.LOW,
                0: TicketPriority.NONE,
            }
            priority = priority_map.get(linear_priority, TicketPriority.NONE)

            # Extract labels
            labels = []
            if "labels" in issue:
                if isinstance(issue["labels"], list):
                    labels = [
                        l.get("name", l) if isinstance(l, dict) else l
                        for l in issue["labels"]
                    ]

            ticket = LinearTicket(
                id=issue["id"],
                identifier=issue.get("identifier", f"RAV-{issue['id'][:4]}"),
                title=issue["title"],
                description=issue.get("description"),
                priority=priority,
                state=issue.get("state", {}).get("name", "Backlog") if isinstance(issue.get("state"), dict) else issue.get("state", "Backlog"),
                labels=labels,
                estimate=issue.get("estimate"),
                assignee_id=issue.get("assignee", {}).get("id") if isinstance(issue.get("assignee"), dict) else issue.get("assignee"),
                url=issue.get("url", f"https://linear.app/ravenhelm/issue/{issue.get('identifier', '')}"),
                created_at=datetime.fromisoformat(issue["createdAt"].replace("Z", "+00:00")) if issue.get("createdAt") else datetime.utcnow(),
                updated_at=datetime.fromisoformat(issue["updatedAt"].replace("Z", "+00:00")) if issue.get("updatedAt") else datetime.utcnow(),
            )
            tickets.append(ticket)

        self.backlog = tickets
        return tickets

    def get_ready_tickets(self, limit: int = 10) -> list[LinearTicket]:
        """
        Get tickets that are ready to be worked on.
        Filters for Todo status and sorts by priority.
        """
        ready = [
            t for t in self.backlog
            if t.state in [LinearState.TODO.value, LinearState.BACKLOG.value]
        ]

        # Sort by priority (URGENT first, then HIGH, etc.)
        priority_order = {
            TicketPriority.URGENT: 0,
            TicketPriority.HIGH: 1,
            TicketPriority.MEDIUM: 2,
            TicketPriority.LOW: 3,
            TicketPriority.NONE: 4,
        }

        ready.sort(key=lambda t: priority_order.get(t.priority, 5))
        return ready[:limit]

    def create_sprint(
        self,
        name: str,
        goal: str,
        ticket_ids: list[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> SprintPlan:
        """
        Create a sprint plan from selected tickets.
        """
        tickets = [t for t in self.backlog if t.id in ticket_ids or t.identifier in ticket_ids]

        total_estimate = sum(t.estimate or 0 for t in tickets)

        self.current_sprint = SprintPlan(
            sprint_name=name,
            sprint_goal=goal,
            tickets=tickets,
            total_estimate_hours=total_estimate if total_estimate > 0 else None,
            start_date=start_date,
            end_date=end_date,
        )

        return self.current_sprint

    async def dispatch_sprint(self) -> list:
        """
        Dispatch all tickets in the current sprint to agents.
        """
        if not self.current_sprint:
            raise ValueError("No sprint plan set. Call create_sprint first.")

        assignments = []

        for ticket in self.current_sprint.tickets:
            assignment = await self.orchestrator.assign_ticket(ticket)
            assignments.append(assignment)

        return assignments

    async def dispatch_ticket(self, ticket_identifier: str):
        """
        Dispatch a single ticket by its identifier (e.g., RAV-17).
        """
        ticket = next(
            (t for t in self.backlog if t.identifier == ticket_identifier),
            None
        )

        if not ticket:
            raise ValueError(f"Ticket {ticket_identifier} not found in backlog")

        return await self.orchestrator.assign_ticket(ticket)

    def get_agent_recommendations(self) -> dict[ClaudeAgentRole, list[str]]:
        """
        Get recommended ticket assignments by agent type.
        """
        recommendations: dict[ClaudeAgentRole, list[str]] = {
            role: [] for role in ClaudeAgentRole
        }

        for ticket in self.get_ready_tickets(limit=50):
            agent = self.orchestrator.determine_agent_for_ticket(ticket)
            recommendations[agent].append(ticket.identifier)

        return {k: v for k, v in recommendations.items() if v}

    def get_phase_0_tickets(self) -> list[LinearTicket]:
        """
        Get Phase 0 (Foundation) tickets - RAV-17, RAV-18, RAV-19.
        These are the critical path items that unblock all other work.
        """
        phase_0_ids = ["RAV-17", "RAV-18", "RAV-19"]
        return [t for t in self.backlog if t.identifier in phase_0_ids]


# Workflow rules enforcer
class WorkflowRules:
    """
    Enforces the ticket-based workflow rules:
    - Agents only work assigned tickets
    - Work is reported back to dispatcher
    - Exceptions for SRE and Product Lead roles
    """

    @staticmethod
    def can_work_without_ticket(agent: ClaudeAgentRole) -> bool:
        """Check if agent can work without an assigned ticket."""
        return agent in AUTONOMOUS_ROLES

    @staticmethod
    def validate_work_request(
        agent: ClaudeAgentRole,
        ticket_identifier: Optional[str],
        orchestrator: TicketOrchestrator,
    ) -> tuple[bool, str]:
        """
        Validate whether an agent can perform work.

        Returns:
            (is_valid, reason)
        """
        # Autonomous roles can always work
        if WorkflowRules.can_work_without_ticket(agent):
            return True, f"{agent.value} is an autonomous role"

        # For other roles, ticket must be assigned
        if not ticket_identifier:
            return False, f"{agent.value} requires an assigned ticket"

        # Check ticket is assigned to this agent
        assignment = None
        for a in orchestrator.assigned_tickets.values():
            if a.ticket.identifier == ticket_identifier:
                assignment = a
                break

        if not assignment:
            return False, f"Ticket {ticket_identifier} is not assigned"

        if assignment.assigned_agent != agent:
            return False, f"Ticket {ticket_identifier} is assigned to {assignment.assigned_agent.value}, not {agent.value}"

        return True, "Work authorized"


# Summary output for conversation context
def format_dispatcher_summary(dispatcher: LinearDispatcher) -> str:
    """
    Format a summary of the current dispatcher state for conversation output.
    """
    board = dispatcher.whiteboard.get_board_state()

    lines = [
        "=" * 60,
        "📋 WHITEBOARD STATUS",
        "=" * 60,
        "",
        f"⏰ Timestamp: {board['timestamp']}",
        "",
        "📊 Ticket Summary:",
        f"   Backlog:     {len(board['tickets']['backlog'])}",
        f"   In Progress: {len(board['tickets']['in_progress'])}",
        f"   Blocked:     {len(board['tickets']['blocked'])}",
        f"   Completed:   {board['tickets']['completed']}",
        "",
    ]

    if board['tickets']['in_progress']:
        lines.append("🚀 Active Work:")
        for work in board['tickets']['in_progress']:
            lines.append(f"   {work['identifier']} → {work['agent']}")
            lines.append(f"      {work['summary']}")
        lines.append("")

    if board['tickets']['blocked']:
        lines.append("🚫 Blocked Items:")
        for blocked in board['tickets']['blocked']:
            lines.append(f"   {blocked['identifier']}: {blocked['reason']}")
        lines.append("")

    lines.append("👥 Agent Status:")
    for agent, status in board['agent_status'].items():
        state_emoji = {
            "working": "🔨",
            "idle": "💤",
            "queued": "📥",
        }.get(status['state'], "❓")

        autonomous_tag = " (autonomous)" if status['autonomous'] else ""
        queue_info = f" [{status['queue_size']} queued]" if status['queue_size'] > 0 else ""

        lines.append(f"   {state_emoji} {agent}: {status['state']}{queue_info}{autonomous_tag}")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)
