# AI_RULES.md

## Repo
C:\Users\twone\Desktop\E_YAY CODEX

## Core Philosophy
- Minimum token.
- Maximum useful work.
- Minimum time.
- Minimum error.
- Read only what is needed.
- Do not reread old chat history.
- Do not scan the whole repo unless needed.
- Prefer small, mechanical, test-protected changes.

## Default Read Order
For every task:
1. Read AI_CONTEXT.md first.
2. Read AI_RULES.md second.
3. Read AI_TASK_LOG.md only if history is needed.
4. Read NEXT_TASK.md only if the task depends on current backlog.
5. Read HANDOFF_STATE.md only if checkpoint verification is needed.
6. Read README.md only around the relevant section.
7. Inspect only files related to the task.

## Default Working Mode
- Work directly inside this repo.
- Edit files directly when implementation is requested.
- Do not only explain when asked to implement.
- Do not ask for confirmation for routine safe edits inside this repo.
- Ask only before:
  - deleting many files
  - editing outside this repo
  - installing global packages
  - using network
  - exposing server publicly
  - changing system settings
  - changing execution/trading permissions

## Safety Rules
- No live market data.
- No network calls unless explicitly allowed.
- No trading execution.
- No broker integration.
- No order placement.
- No portfolio mutation.
- No AI buy/sell decision.
- Preserve PAPER_ONLY.
- Preserve REPLAY_ONLY.
- Preserve NO_EXECUTION.
- Preserve LOCAL_ONLY where applicable.
- Preserve paper_safe=True, network_calls=False, execution_side_effects="NO_EXECUTION".

## Code Rules
- Do not use wildcard imports.
- Do not remove public re-exports blindly.
- If public re-exports are intentional, preserve them and update __all__.
- Do not change API route paths unless fixing a proven registration bug.
- Do not change response field names unless tests require a documented correction.
- Do not import API route modules into service logic.
- Prefer explicit imports.
- Avoid circular imports.
- Keep deterministic ordering.
- Do not refactor unless the task explicitly says refactor or a file is clearly above cleanup threshold.
- Do not add diagnostics unless the task explicitly says diagnostic.
- Do not add dashboard unless the task explicitly says dashboard.

## Validation Commands
After code changes run:

ruff check backend tests

pytest -p no:cacheprovider --basetemp=".pytest_tmp\basetemp"

python scripts/verify_and_snapshot.py

## Failure Handling
- If ruff fails, fix only reported ruff issues.
- If pytest fails, fix collection/import errors first.
- If verify_and_snapshot fails, inspect the failure and fix the minimal cause.
- Rerun only what is needed.
- Run full validation at the end.
- Do not start unrelated cleanup.

## Final Report Format
- exact task performed
- files edited
- ruff result
- pytest result
- verify_and_snapshot result
- new clean backup path
- whether only latest backup remains
- remaining caveat/error
- recommended next task
