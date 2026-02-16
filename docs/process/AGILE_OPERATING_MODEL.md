# Ravenhelm Agile Operating Model

_Last updated: 2025-12-03_

This document explains how the Ravenhelm / Hliðskjálf project uses GitLab to run an Agile delivery workflow. It maps GitLab primitives (issues, labels, milestones, boards, reports) to Scrum/Kanban concepts, describes the standardized taxonomy, and provides templates plus OKR guidance.

---

## 1. Core Taxonomy

| Agile Concept | GitLab Representation | Notes |
| --- | --- | --- |
| **Work Item Types** | Scoped labels `type::story`, `type::task`, `type::bug`, `type::chore`, `type::epic` | Apply exactly one type label to every issue for filtering/reporting. |
| **Workflow State** | Scoped labels `workflow::backlog`, `workflow::ready`, `workflow::in_progress`, `workflow::review`, `workflow::blocked`, `workflow::done` | These drive the issue boards; move a card by changing its workflow label. |
| **Areas / Streams** | Optional scoped labels such as `area::platform`, `area::ui`, `area::ai` | Enables slice-and-dice on the same board. |
| **Story Points / Effort** | Issue weights (Fibonacci 1/2/3/5/8/13) | Enable in project settings → Issues. Required for burndown charts. |
| **Sprints** | Project milestones (two-week cadence) | Example: `Sprint 2025-12-01` (start 2025-12-01, due 2025-12-12). |
| **Epics / Initiatives** | Issues tagged `type::epic` with related-story links (until native epics become available) | See issues `#57` and `#58` for live examples. |

### Workflow Rules
1. Newly captured work → `workflow::backlog`.
2. Once groomed (clear scope, acceptance criteria, weight) → `workflow::ready`.
3. Assignee starts work → `workflow::in_progress`.
4. When awaiting verification/review → `workflow::review`.
5. Blocked by external dependency → replace current workflow label with `workflow::blocked` (and add comment).
6. After acceptance / deploy → `workflow::done` (done column auto-closes when milestone completes).

---

## 2. Boards & Filters

Three project boards now exist under **Issue Boards**:

1. **Sprint Board** (Board ID 3)  
   - Scope: milestone = current sprint (`Sprint 2025-12-01`).  
   - Lists: `workflow::ready → workflow::in_progress → workflow::review → workflow::blocked → workflow::done`.  
   - Usage: daily stand-ups, in-flight work.

2. **Backlog Board** (Board ID 4)  
   - Lists: `workflow::backlog`, `workflow::ready`.  
   - Usage: backlog refinement and sprint planning. Drag cards to reprioritize.

3. **Ops Board** (Board ID 5)  
   - Filter: label `area::platform`.  
   - Lists mirror the sprint board but isolate platform/operations work for quick triage.

Each board still exposes GitLab’s default Backlog/Closed lists (toggle per board if we want a pure Kanban surface).

### 2.1 Viewing Modes & Filters

You can duplicate an existing board or create a new one for any slice of work. GitLab boards can be scoped simultaneously by **milestone**, **iteration**, **label(s)**, and/or **assignee**, so we standardize on the following views:

| View | Purpose | Filter / Scope | Lists & Notes |
| --- | --- | --- | --- |
| **Product Backlog** | Groom and prioritize upcoming work | No milestone, optional `type::story`/`type::bug` label filter | `workflow::backlog` → `workflow::ready`. (Board ID 4) |
| **Sprint Execution** | Daily stand-up + burndown alignment | Milestone = current sprint (e.g., `Sprint 2025-12-01`) | `workflow::ready` → `workflow::done`. (Board ID 3) |
| **Epic / Initiative View** | Track strategic initiatives | Board filtered by `labels=type::epic` (add optional `okr::<slug>` or `release::<version>`) | Same workflow lists; cards represent epics and can be expanded via related issues. |
| **Release Readiness** | Ensure release scope is green | Filter by release milestone or `labels=release::<version>` | Duplicate sprint board, but include QA-specific list if needed. Burndown uses the release milestone. |
| **Ops / Triage** | Platform incidents, maintenance, infra tasks | `labels=area::platform` (Board ID 5) | Ready → In Progress → Review → Done. Great for ad-hoc handoffs. |
| **OKR Slice** | Inspect progress on a single objective | `labels=okr::<objective>` (stackable with milestone filter) | Use the same workflow lists; this is an on-demand view to discuss KR health. |

Tips:
- You can combine filters (e.g., `milestone=Sprint 2025-12-01` + `labels=okr::platform-uptime`) to see only the sprint stories tied to a particular KR.
- Boards remember their filter state per user; pin the views you care about in the left-hand board selector.
- To answer “epics only?” simply open the Epic board (or apply `labels=type::epic` via the UI) and you’ll get the same workflow columns but with initiative cards instead of stories.

### 2.2 Norns Work Queue

We route automation tasks to the Norns via GitLab labels:

1. Create/groom an issue as usual, then apply:
   - `actor::norns` (signals ownership by the LangGraph agents)
   - `workflow::ready` (only ready cards will be delivered)
   - The owning epic label (for traceability).
2. The saved **“Norns Queue”** board filters to `labels=actor::norns` and shows only `workflow::ready → done`. Share this view with humans who want to monitor the bots’ backlog.
3. When the issue moves to `workflow::ready`, GitLab’s webhook hits `https://norns.ravenhelm.test/api/work-items`. Bifrost acknowledges the issue, flips it to `workflow::in_progress`, and posts an audit comment.
4. When the agent finishes and updates the workflow to `workflow::done`, the queue clears automatically.

> 💡 Leave the issue unassigned (or assign to “Norns”) so human workload reports stay accurate.

---

## 3. Cadence & Ceremonies

| Ceremony | Frequency | GitLab Actions |
| --- | --- | --- |
| **Backlog Grooming** | Weekly | Review issue list filtered by `workflow::backlog`, estimate, add acceptance criteria, move to `workflow::ready`. |
| **Sprint Planning** | Every 2 weeks | Duplicate the next milestone, set dates, assign capacity (weights), pull top `workflow::ready` issues into the milestone & board. |
| **Daily Stand-up** | Daily | Walk the Sprint Board columns, update statuses, call out `workflow::blocked`. |
| **Sprint Review / Demo** | End of sprint | Filter milestone issues at `workflow::done`, demo, gather feedback, close milestone. |
| **Retrospective** | End of sprint | Capture retro items as `type::chore` issues (label `workflow::backlog`). |

Burndown charts are available per milestone (Issues → Milestones → `Sprint …`). They rely on weights and due dates, so ensure every committed issue has both.

---

## 4. Templates

Use these markdown snippets when creating issues. Copy/paste into the description field.

### 4.1 User Story (`type::story`)
```
## Summary
As a <persona>, I want <capability> so that <value>.

## Acceptance Criteria
- [ ] ...
- [ ] ...

## Notes
- Links / references

## Definition of Done
- [ ] Tests/validation
- [ ] Documentation updated
```

### 4.2 Bug (`type::bug`)
```
## Observed Behavior

## Expected Behavior

## Steps to Reproduce
1.
2.

## Environment
- Version / branch
- Logs / screenshots

## Impact / Severity
```

### 4.3 Task / Chore (`type::task` or `type::chore`)
```
## Objective

## Deliverables
- [ ] ...

## Dependencies
- Issue #XX
```

### 4.4 Lightweight Epic (`type::epic`)
```
## Vision

## Success Metrics
- KPI / OKR alignment

## Scope
- Story #...
- Story #...

## Out of Scope
- ...
```

---

## 5. OKRs Integration

We track Objectives and Key Results quarterly, cascading them to epics and stories:

1. **Define OKRs at the group level** (e.g., “Objective: Deliver zero-trust MCP platform”). Store them in `docs/process/OKRS-2025Q1.md` (to be created per quarter) and mirror each OKR as a `type::epic` issue for live tracking.
2. **Map key results to GitLab metrics**:  
   - KR1: “100% MCP traffic via OAuth+mTLS” → link Epic #57 plus completion percentage.  
   - KR2: “Reduce platform incident MTTR to < 15 min” → tie to Ops stories (#61/#62) and Grafana alerting work.
3. **Tag issues with `okr::<objective slug>` labels** to filter per KR on boards/reports.
4. **Review cadence**: during sprint review, update KR progress (percentage complete, leading indicators) inside the OKR document + epic description. Summarize in milestone closeout notes.

This hybrid keeps strategic intent (OKRs) in docs with narrative context while allowing day-to-day execution through issues/boards.

---

## 6. Operating Checklist

1. **Intake**: create issue → apply `type::` + `area::` labels → set `workflow::backlog` → optionally add `okr::`.
2. **Refine**: add story template, weight, dependencies, convert to `workflow::ready`.
3. **Plan Sprint**: assign milestone, confirm capacity, ensure board placement.
4. **Execute**: update workflow label as work progresses; comment when blocked.
5. **Review**: close issues (or move to `workflow::done`), update OKR progress, close milestone, archive completed board columns if desired.

Following this model keeps GitLab as the single source of truth for Agile delivery, auditability, and executive reporting.

