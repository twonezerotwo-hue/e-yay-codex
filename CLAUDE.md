# CLAUDE FAST CONTEXT

Read this file first. Do not start with broad repo reads.

## Repo
- Path: `C:\Users\twone\Desktop\E_YAY CODEX`
- GitHub: `https://github.com/twonezerotwo-hue/e-yay-codex`
- Branch: `main`
- Synced local commit: `ea45a44`

## Read Order
1. Read this file.
2. Read the user task.
3. Use `rg` to find only directly related files.
4. Read `NEXT_TASK.md` only for backlog/state work.
5. Read `AI_CONTEXT.md` or `HANDOFF_STATE.md` only for explicit checkpoint/context needs.
6. Do not open `README.md`, `SYSTEM_ARCHITECTURE.md`, or archived logs unless the task requires docs or deep architecture review.

## System Boundary
- Decision-support system, not an autonomous trading engine.
- AI explains; deterministic code owns decisions.
- Preserve `PAPER_ONLY`, `REPLAY_ONLY`, `NO_EXECUTION`.
- No broker integration or real order placement.
- Do not add live/network data unless the user explicitly asks for it.

## Working Rules
- Prefer the smallest useful diff.
- Avoid broad repo scans.
- Preserve endpoint paths, response field names, and public imports unless the task explicitly changes them.
- Do not use wildcard imports.
- Do not import API route modules into service logic.
- Run narrow tests first; run full validation only when runtime code changed.

## Current Local State
- The repo was synced to GitHub `main` on `2026-06-06`.
- Latest existing clean backup: `C:\Users\twone\Desktop\E_YAY CODEX\clean_backups\eyay_clean_20260528T135613Z.zip`
- Historical handoff/task logs were archived to `docs/claude_archive/`.

## Next High-Value Fix
- Make `GET /api/v1/trading/state` read-only.
- Move paper-trading tick/training side effects to explicit `POST` endpoints.
- Keep `PAPER_SAFE / NO_EXECUTION`.

## Validation
- Docs-only changes: no runtime tests required.
- Runtime/backend changes:
```powershell
ruff check backend tests
pytest -p no:cacheprovider --basetemp=".pytest_tmp\basetemp"
```
- Clean checkpoint:
```powershell
python scripts/verify_and_snapshot.py
```
