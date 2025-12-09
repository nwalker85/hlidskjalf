# Whiteboard System - Agent Coordination Architecture

## Overview

The Whiteboard System provides ticket-based coordination between Claude Code agents and the Linear project management system. It implements a "dispatcher" pattern where work is assigned, tracked, and reported through a shared visibility layer.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         LINEAR                                   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │ RAV-17  │  │ RAV-18  │  │ RAV-19  │  │ RAV-XX  │  ...       │
│  │ Todo    │  │ Todo    │  │ Todo    │  │ Backlog │            │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘            │
└───────┼────────────┼────────────┼────────────┼──────────────────┘
        │            │            │            │
        ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LINEAR DISPATCHER                             │
│  • Pulls tickets from Linear API                                │
│  • Filters by state (Todo, Backlog)                             │
│  • Sorts by priority (Urgent → High → Medium → Low)             │
│  • Creates sprint plans                                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TICKET ORCHESTRATOR                            │
│  • Matches tickets to agents by label                           │
│  • Publishes assignment events to Redpanda                      │
│  • Tracks work progress                                          │
│  • Reports completion back to dispatcher                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  frontend-ui  │  │  solution-    │  │  fullstack-   │
│  -designer    │  │  architect    │  │  project-lead │
│               │  │               │  │               │
│  RAV-17       │  │  RAV-19       │  │  RAV-20+      │
│  RAV-18       │  │               │  │               │
└───────────────┘  └───────────────┘  └───────────────┘
```

## Core Components

### 1. Linear Dispatcher (`linear_dispatcher.py`)

The dispatcher is the "product lead" side of the system:

```python
from src.norns.linear_dispatcher import LinearDispatcher, WorkflowRules

dispatcher = LinearDispatcher(orchestrator, team_id="3f8d849b-c1f6-4be8-b2fe-b65246fe3876")

# Load backlog from Linear API response
tickets = dispatcher.load_backlog(issues_from_linear)

# Get ready tickets (Todo/Backlog, sorted by priority)
ready = dispatcher.get_ready_tickets(limit=10)

# Create a sprint
sprint = dispatcher.create_sprint(
    name="Sprint 1 - Foundation",
    goal="Complete Phase 0 accessibility and ADR work",
    ticket_ids=["RAV-17", "RAV-18", "RAV-19"]
)

# Dispatch to agents
assignments = await dispatcher.dispatch_sprint()
```

### 2. Ticket Orchestrator (`ticket_orchestrator.py`)

The orchestrator handles assignment and tracking:

```python
from src.norns.ticket_orchestrator import (
    TicketOrchestrator,
    Whiteboard,
    create_work_report,
    ClaudeAgentRole,
)

orchestrator = TicketOrchestrator(kafka_bootstrap="redpanda:9092")
await orchestrator.connect()

# Assign a ticket
assignment = await orchestrator.assign_ticket(ticket)

# Get whiteboard state
whiteboard = Whiteboard(orchestrator)
state = whiteboard.get_board_state()
```

### 3. Whiteboard (`ticket_orchestrator.py:Whiteboard`)

Shared visibility for all agents:

```python
{
    "timestamp": "2025-12-09T22:00:00Z",
    "tickets": {
        "backlog": [...],      # Assigned but not started
        "in_progress": [...],  # Currently being worked
        "blocked": [...],      # Stuck on dependencies
        "completed": 5         # Count of done tickets
    },
    "agent_status": {
        "frontend-ui-designer": {"state": "working", "queue_size": 2, "autonomous": false},
        "solution-architect": {"state": "idle", "queue_size": 1, "autonomous": false},
        "sre-incident-resolver": {"state": "idle", "queue_size": 0, "autonomous": true}
    }
}
```

## Workflow Rules

### Standard Agents (Ticket Required)

| Agent | Labels | Description |
|-------|--------|-------------|
| `frontend-ui-designer` | accessibility, mobile, visual, ux | UI/UX work |
| `fullstack-project-lead` | refactor, console | Full-stack implementation |
| `solution-architect` | foundation | Architecture decisions |
| `sre-incident-resolver` | performance | Performance issues |

**Rule:** These agents MUST have an assigned ticket to work. They report progress back to the dispatcher.

### Autonomous Agents (No Ticket Required)

| Agent | Description |
|-------|-------------|
| `sre-incident-resolver` | Can respond to incidents without tickets |
| `agile-product-lead` | Can prioritize and plan without tickets |

**Rule:** These agents can work proactively without assigned tickets.

### Validation

```python
from src.norns.linear_dispatcher import WorkflowRules

# Check if work is authorized
is_valid, reason = WorkflowRules.validate_work_request(
    agent=ClaudeAgentRole.FRONTEND_UI_DESIGNER,
    ticket_identifier="RAV-17",
    orchestrator=orchestrator
)

if not is_valid:
    raise PermissionError(reason)
```

## Label-to-Agent Mapping

```python
LABEL_TO_AGENT = {
    "accessibility": ClaudeAgentRole.FRONTEND_UI_DESIGNER,
    "mobile": ClaudeAgentRole.FRONTEND_UI_DESIGNER,
    "visual": ClaudeAgentRole.FRONTEND_UI_DESIGNER,
    "ux": ClaudeAgentRole.FRONTEND_UI_DESIGNER,
    "refactor": ClaudeAgentRole.FULLSTACK_PROJECT_LEAD,
    "console": ClaudeAgentRole.FULLSTACK_PROJECT_LEAD,
    "foundation": ClaudeAgentRole.SOLUTION_ARCHITECT,
    "performance": ClaudeAgentRole.SRE_INCIDENT_RESOLVER,
}
```

## Event Topics (Redpanda)

| Topic | Description |
|-------|-------------|
| `ravenhelm.tickets.assigned` | Ticket assigned to agent |
| `ravenhelm.tickets.started` | Agent started work |
| `ravenhelm.tickets.progress` | Work progress update |
| `ravenhelm.tickets.completed` | Work completed |
| `ravenhelm.tickets.blocked` | Work blocked |
| `ravenhelm.tickets.dispatcher` | Dispatcher reports |

## Work Reports

Agents report progress using `WorkReport`:

```python
report = create_work_report(
    ticket_id="b18f7a71-5a24-454d-ab3f-e11ff1ee210e",
    ticket_identifier="RAV-17",
    agent=ClaudeAgentRole.FRONTEND_UI_DESIGNER,
    status="completed",  # started, progress, completed, blocked
    summary="Fixed WCAG AA color contrast violations",
    files_modified=["tailwind.config.ts", "globals.css"],
    time_spent_minutes=120,
)

await orchestrator.process_work_report(report)
```

## Sprint Planning

### Current Sprint: Sprint 1 - Foundation (Phase 0)

| Ticket | Title | Agent | Priority |
|--------|-------|-------|----------|
| RAV-17 | Fix WCAG AA color contrast violations | frontend-ui-designer | Urgent |
| RAV-18 | Add comprehensive keyboard navigation | frontend-ui-designer | Urgent |
| RAV-19 | Create ADR documenting refactoring strategy | solution-architect | Urgent |

### Phase Progression

1. **Phase 0 (Foundation):** RAV-17, RAV-18, RAV-19 - Accessibility + ADR
2. **Phase 1 (Core Extraction):** RAV-20 - RAV-25 - Component decomposition
3. **Phase 2 (State Management):** RAV-26 - RAV-30 - Context/hooks
4. **Phase 3 (Polish):** RAV-31 - RAV-36 - Mobile + performance

## Files

- `/src/norns/ticket_orchestrator.py` - Core orchestration
- `/src/norns/linear_dispatcher.py` - Linear integration
- `/src/norns/squad_schema.py` - Event schemas
- `/src/norns/event_driven_orchestrator.py` - Claude orchestrator

## Related

- [Linear Team: Ravenhelm](https://linear.app/ravenhelm)
- Team ID: `3f8d849b-c1f6-4be8-b2fe-b65246fe3876`
