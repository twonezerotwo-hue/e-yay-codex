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
- Agent must self-validate; the user should not need to audit internal field/tool/route correctness manually.
- Preserve `PAPER_ONLY`, `REPLAY_ONLY`, `NO_EXECUTION`.
- Preserve `paper_safe=True`, `network_calls=False`, `execution_side_effects="NO_EXECUTION"` where those contracts apply.
- For paper-trading opens, require a 60-second warning/reject window before opening.
- Do not open XAUUSD, XAGUSD, BRENT, or XCUUSD during the weekend closure window (Friday 21:00 UTC to Sunday 22:00 UTC).

## Code
- No wildcard imports.
- Preserve public contracts unless the task explicitly changes them.
- Do not import route modules into service logic.
- Keep deterministic ordering.
