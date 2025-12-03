# Incident Library

Use this page to capture every production incident following ITIL v4 practices.

## Template
```
## Incident YYYY-MM-DD – <Short Title>
- **Severity:** P0/P1/P2/P3
- **Services:** (list affected services/agents)
- **Timeline:** key events w/ timestamps
- **Root Cause:** summary + links to evidence
- **Mitigations:** what restored service
- **Follow-ups:** link to GitLab issues
```

## Process
1. Create GitLab issue using `Incident` template (Repo → Issues → New → Incident).
2. Apply labels `status::in-progress`, `priority::<level>`, `incident`.
3. Update this wiki page with summary + link once incident is closed.
4. Record lessons in `docs/LESSONS_LEARNED.md` and update relevant runbooks.

