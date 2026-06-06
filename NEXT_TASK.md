# NEXT TASK

Next task:
- Make `GET /api/v1/trading/state` read-only.
- Move paper-trading tick and training mutations to explicit `POST` endpoints.
- Preserve `PAPER_SAFE / NO_EXECUTION`.

Why this next:
- Current behavior mutates state inside a `GET`.
- That weakens API semantics and execution-isolation discipline.

Historical backlog archive:
- `docs/claude_archive/NEXT_TASK_20260606.md`
