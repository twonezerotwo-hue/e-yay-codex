# AI_RULES

Use `CLAUDE.md` as the primary operating file.

## Defaults
- Minimum token use.
- Maximum useful work.
- Small diffs.
- No broad scans unless needed.

## Safety
- No trading execution.
- No broker integration.
- No AI buy/sell authority.
- Preserve `PAPER_ONLY`, `REPLAY_ONLY`, `NO_EXECUTION`.
- Preserve `paper_safe=True`, `network_calls=False`, `execution_side_effects="NO_EXECUTION"` where those contracts apply.

## Code
- No wildcard imports.
- Preserve public contracts unless the task explicitly changes them.
- Do not import route modules into service logic.
- Keep deterministic ordering.
