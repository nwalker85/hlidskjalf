"""
Ticket Orchestrator - Linear Integration for Agent Task Assignment

This module bridges the Linear project management system with the Norns agent
orchestration system, implementing the "whiteboard" pattern where:
1. Tickets are the source of truth for work
2. Agents only work assigned tickets
3. Work is reported back to the dispatcher

Exceptions: SRE and Product Lead roles can work without assigned tickets.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Optional, Any
from uuid import uuid4
from enum import Enum

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from pydantic import BaseModel, Field

from src.norns.squad_schema import (
    AgentRole,
    AgentEvent,
    EventType,
    TaskAssignment,
    Topics,
)


# New topics for ticket orchestration
class TicketTopics:
    """Redpanda topics for ticket-based coordination"""
    TICKET_ASSIGNED = "ravenhelm.tickets.assigned"
    TICKET_STARTED = "ravenhelm.tickets.started"
    TICKET_PROGRESS = "ravenhelm.tickets.progress"
    TICKET_COMPLETED = "ravenhelm.tickets.completed"
    TICKET_BLOCKED = "ravenhelm.tickets.blocked"
    DISPATCHER_REPORT = "ravenhelm.tickets.dispatcher"


class TicketPriority(str, Enum):
    """Maps Linear priority to urgency levels"""
    URGENT = "urgent"      # Linear priority 1
    HIGH = "high"          # Linear priority 2
    MEDIUM = "medium"      # Linear priority 3
    LOW = "low"            # Linear priority 4
    NONE = "none"          # Linear priority 0


class ClaudeAgentRole(str, Enum):
    """Claude Code agent types that can be assigned tickets"""
    FRONTEND_UI_DESIGNER = "frontend-ui-designer"
    FULLSTACK_PROJECT_LEAD = "fullstack-project-lead"
    SOLUTION_ARCHITECT = "solution-architect"
    TECHNICAL_WRITER = "technical-writer"
    SRE_INCIDENT_RESOLVER = "sre-incident-resolver"
    AGILE_PRODUCT_LEAD = "agile-product-lead"
    CLAUDE_SKILL_BUILDER = "claude-skill-builder"
    MCP_SERVER_ARCHITECT = "mcp-server-architect"
    GENERAL_PURPOSE = "general-purpose"
    EXPLORE = "Explore"
    PLAN = "Plan"


# Agents that can work without tickets (exception roles)
AUTONOMOUS_ROLES = {
    ClaudeAgentRole.SRE_INCIDENT_RESOLVER,
    ClaudeAgentRole.AGILE_PRODUCT_LEAD,
}


class LinearTicket(BaseModel):
    """Represents a Linear issue for agent assignment"""
    id: str = Field(..., description="Linear issue ID")
    identifier: str = Field(..., description="Human-readable ID like RAV-17")
    title: str
    description: Optional[str] = None
    priority: TicketPriority = TicketPriority.NONE
    state: str = "Backlog"
    labels: list[str] = Field(default_factory=list)
    estimate: Optional[int] = None  # Story points / hours
    assignee_id: Optional[str] = None
    url: str
    created_at: datetime
    updated_at: datetime


class TicketAssignment(BaseModel):
    """Assignment of a ticket to an agent"""
    ticket: LinearTicket
    assigned_agent: ClaudeAgentRole
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_by: str = "ticket-orchestrator"
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))


class WorkReport(BaseModel):
    """Report from an agent about work on a ticket"""
    ticket_id: str
    ticket_identifier: str
    agent: ClaudeAgentRole
    status: str  # started, progress, completed, blocked
    summary: str
    details: Optional[dict[str, Any]] = None
    files_modified: list[str] = Field(default_factory=list)
    time_spent_minutes: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DispatcherEvent(BaseModel):
    """Event structure for dispatcher communication"""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str  # ticket_assigned, work_started, work_completed, work_blocked
    ticket_identifier: str
    agent: ClaudeAgentRole
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Label to agent role mapping
LABEL_TO_AGENT: dict[str, ClaudeAgentRole] = {
    "accessibility": ClaudeAgentRole.FRONTEND_UI_DESIGNER,
    "mobile": ClaudeAgentRole.FRONTEND_UI_DESIGNER,
    "visual": ClaudeAgentRole.FRONTEND_UI_DESIGNER,
    "ux": ClaudeAgentRole.FRONTEND_UI_DESIGNER,
    "refactor": ClaudeAgentRole.FULLSTACK_PROJECT_LEAD,
    "console": ClaudeAgentRole.FULLSTACK_PROJECT_LEAD,
    "foundation": ClaudeAgentRole.SOLUTION_ARCHITECT,
    "performance": ClaudeAgentRole.SRE_INCIDENT_RESOLVER,
}


class TicketOrchestrator:
    """
    Orchestrates ticket-based work assignment for Claude Code agents.

    Workflow:
    1. Poll Linear for prioritized backlog
    2. Match tickets to appropriate agent roles based on labels
    3. Publish assignment events to Redpanda
    4. Track work progress and completion
    5. Report back to dispatcher
    """

    def __init__(
        self,
        kafka_bootstrap: str = "redpanda:9092",
        linear_team_id: str = "3f8d849b-c1f6-4be8-b2fe-b65246fe3876",  # Ravenhelm
    ):
        self.kafka_bootstrap = kafka_bootstrap
        self.linear_team_id = linear_team_id
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None

        # State tracking
        self.assigned_tickets: dict[str, TicketAssignment] = {}
        self.in_progress_tickets: dict[str, WorkReport] = {}
        self.completed_tickets: dict[str, WorkReport] = {}
        self.blocked_tickets: dict[str, WorkReport] = {}

        # Agent work queues
        self.agent_queues: dict[ClaudeAgentRole, list[LinearTicket]] = {
            role: [] for role in ClaudeAgentRole
        }

    async def connect(self):
        """Connect to Redpanda for event streaming"""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.kafka_bootstrap,
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
        )
        await self.producer.start()

        self.consumer = AIOKafkaConsumer(
            TicketTopics.TICKET_STARTED,
            TicketTopics.TICKET_PROGRESS,
            TicketTopics.TICKET_COMPLETED,
            TicketTopics.TICKET_BLOCKED,
            bootstrap_servers=self.kafka_bootstrap,
            group_id="ticket-orchestrator",
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest'
        )
        await self.consumer.start()

        print("✓ Ticket Orchestrator connected to Redpanda")

    async def disconnect(self):
        """Disconnect from Redpanda"""
        if self.producer:
            await self.producer.stop()
        if self.consumer:
            await self.consumer.stop()
        print("✓ Ticket Orchestrator disconnected")

    def determine_agent_for_ticket(self, ticket: LinearTicket) -> ClaudeAgentRole:
        """
        Determine which agent should work on a ticket based on labels.
        Uses priority: first matching label wins.
        """
        for label in ticket.labels:
            label_lower = label.lower()
            if label_lower in LABEL_TO_AGENT:
                return LABEL_TO_AGENT[label_lower]

        # Default assignments based on priority
        if ticket.priority == TicketPriority.URGENT:
            return ClaudeAgentRole.SRE_INCIDENT_RESOLVER

        # Default to fullstack lead for general work
        return ClaudeAgentRole.FULLSTACK_PROJECT_LEAD

    async def assign_ticket(self, ticket: LinearTicket) -> TicketAssignment:
        """
        Assign a ticket to an appropriate agent and publish event.
        """
        agent = self.determine_agent_for_ticket(ticket)

        assignment = TicketAssignment(
            ticket=ticket,
            assigned_agent=agent,
        )

        # Track assignment
        self.assigned_tickets[ticket.id] = assignment
        self.agent_queues[agent].append(ticket)

        # Publish assignment event
        event = DispatcherEvent(
            event_type="ticket_assigned",
            ticket_identifier=ticket.identifier,
            agent=agent,
            payload={
                "ticket_id": ticket.id,
                "title": ticket.title,
                "priority": ticket.priority.value,
                "labels": ticket.labels,
                "url": ticket.url,
            }
        )

        await self.producer.send_and_wait(
            TicketTopics.TICKET_ASSIGNED,
            value=event.model_dump(mode='json')
        )

        await self.report_to_dispatcher(event)

        print(f"📋 Assigned {ticket.identifier} to {agent.value}")
        return assignment

    async def report_to_dispatcher(self, event: DispatcherEvent):
        """
        Report event to the dispatcher topic for centralized tracking.
        """
        await self.producer.send_and_wait(
            TicketTopics.DISPATCHER_REPORT,
            value=event.model_dump(mode='json')
        )

    async def process_work_report(self, report: WorkReport):
        """
        Process a work report from an agent.
        Updates tracking state and reports to dispatcher.
        """
        event_type = f"work_{report.status}"

        if report.status == "started":
            self.in_progress_tickets[report.ticket_id] = report
        elif report.status == "completed":
            self.completed_tickets[report.ticket_id] = report
            self.in_progress_tickets.pop(report.ticket_id, None)
        elif report.status == "blocked":
            self.blocked_tickets[report.ticket_id] = report
            self.in_progress_tickets.pop(report.ticket_id, None)

        event = DispatcherEvent(
            event_type=event_type,
            ticket_identifier=report.ticket_identifier,
            agent=report.agent,
            payload={
                "summary": report.summary,
                "details": report.details,
                "files_modified": report.files_modified,
                "time_spent_minutes": report.time_spent_minutes,
            }
        )

        await self.report_to_dispatcher(event)

        status_emoji = {
            "started": "🚀",
            "progress": "⏳",
            "completed": "✅",
            "blocked": "🚫",
        }.get(report.status, "📝")

        print(f"{status_emoji} {report.ticket_identifier}: {report.summary}")

    async def monitor_work(self, timeout_seconds: int = 300):
        """
        Monitor incoming work reports from agents.
        """
        start_time = asyncio.get_event_loop().time()

        try:
            async for msg in self.consumer:
                report_data = msg.value
                report = WorkReport(**report_data)
                await self.process_work_report(report)

                # Check timeout
                if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                    print(f"\n⏱️ Monitoring timeout ({timeout_seconds}s)")
                    break

        except asyncio.CancelledError:
            pass

    def get_status_summary(self) -> dict:
        """
        Get current status of all tickets.
        """
        return {
            "assigned": len(self.assigned_tickets),
            "in_progress": len(self.in_progress_tickets),
            "completed": len(self.completed_tickets),
            "blocked": len(self.blocked_tickets),
            "agent_queues": {
                role.value: len(queue)
                for role, queue in self.agent_queues.items()
                if queue
            }
        }

    def can_agent_work_without_ticket(self, agent: ClaudeAgentRole) -> bool:
        """
        Check if an agent role can work without an assigned ticket.
        """
        return agent in AUTONOMOUS_ROLES


# Whiteboard state for agent visibility
class Whiteboard:
    """
    Shared state for agent coordination (the "whiteboard" pattern).

    All agents can see:
    - What tickets are assigned
    - Who is working on what
    - What is blocked and why
    - Completed work
    """

    def __init__(self, orchestrator: TicketOrchestrator):
        self.orchestrator = orchestrator

    def get_board_state(self) -> dict:
        """
        Get the current whiteboard state for agent visibility.
        """
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "tickets": {
                "backlog": [
                    {
                        "identifier": a.ticket.identifier,
                        "title": a.ticket.title,
                        "agent": a.assigned_agent.value,
                        "priority": a.ticket.priority.value,
                    }
                    for a in self.orchestrator.assigned_tickets.values()
                    if a.ticket.id not in self.orchestrator.in_progress_tickets
                ],
                "in_progress": [
                    {
                        "identifier": r.ticket_identifier,
                        "agent": r.agent.value,
                        "summary": r.summary,
                    }
                    for r in self.orchestrator.in_progress_tickets.values()
                ],
                "blocked": [
                    {
                        "identifier": r.ticket_identifier,
                        "agent": r.agent.value,
                        "reason": r.summary,
                    }
                    for r in self.orchestrator.blocked_tickets.values()
                ],
                "completed": len(self.orchestrator.completed_tickets),
            },
            "agent_status": self._get_agent_status(),
        }

    def _get_agent_status(self) -> dict:
        """
        Get the current status of each agent type.
        """
        status = {}
        in_progress = {r.agent for r in self.orchestrator.in_progress_tickets.values()}

        for role in ClaudeAgentRole:
            queue_size = len(self.orchestrator.agent_queues.get(role, []))
            is_working = role in in_progress

            status[role.value] = {
                "state": "working" if is_working else ("idle" if queue_size == 0 else "queued"),
                "queue_size": queue_size,
                "autonomous": role in AUTONOMOUS_ROLES,
            }

        return status


def create_work_report(
    ticket_id: str,
    ticket_identifier: str,
    agent: ClaudeAgentRole,
    status: str,
    summary: str,
    details: Optional[dict] = None,
    files_modified: Optional[list[str]] = None,
    time_spent_minutes: Optional[int] = None,
) -> WorkReport:
    """
    Helper to create a work report for agent use.

    Agents should call this when:
    - Starting work on a ticket
    - Making progress updates
    - Completing a ticket
    - Getting blocked
    """
    return WorkReport(
        ticket_id=ticket_id,
        ticket_identifier=ticket_identifier,
        agent=agent,
        status=status,
        summary=summary,
        details=details,
        files_modified=files_modified or [],
        time_spent_minutes=time_spent_minutes,
    )
