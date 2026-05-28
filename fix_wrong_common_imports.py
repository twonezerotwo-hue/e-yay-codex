from pathlib import Path
import re

base = Path(r"C:\Users\twone\Desktop\E_YAY CODEX\backend\app\services")

bad_module = "app.services.snapshot_replay_source_quality_common"
good_module = "app.services.snapshot_replay_source_common"

constant_names = [
    "CRITICAL_SEVERITY_MIN_RANK",
    "HIGH_SEVERITY_MIN_RANK",
    "INFO_SEVERITY_MAX_RANK",
    "SEVERITY_LABEL_SCORES",
    "WARNING_SEVERITY_MAX_RANK",
    "WARNING_SEVERITY_MIN_RANK",
    "ZERO_SEVERITY_RANK",
    "derive_severity_label_from_rank",
    "severity_label_score",
    "severity_rank_density",
    "severity_rank_spread",
]

targets = [
    base / "snapshot_replay_source_quality_drift.py",
    base / "snapshot_replay_source_quality_reconciliation.py",
]

def remove_names_from_import_block(text: str, module: str, remove_names: list[str]) -> str:
    pattern = re.compile(
        rf"from {re.escape(module)} import \(\n(?P<body>.*?)\n\)",
        re.DOTALL,
    )

    def repl(match):
        body = match.group("body")
        names = []
        for line in body.splitlines():
            item = line.strip().rstrip(",")
            if item and item not in remove_names:
                names.append(item)

        if not names:
            return ""

        return "from " + module + " import (\n    " + ",\n    ".join(sorted(set(names))) + ",\n)"

    return pattern.sub(repl, text)

def add_good_import(text: str, module: str, names: list[str]) -> str:
    needed = [name for name in names if name in text]
    if not needed:
        return text

    existing_pattern = re.compile(
        rf"from {re.escape(module)} import \(\n(?P<body>.*?)\n\)",
        re.DOTALL,
    )
    match = existing_pattern.search(text)

    if match:
        existing = []
        for line in match.group("body").splitlines():
            item = line.strip().rstrip(",")
            if item:
                existing.append(item)
        merged = sorted(set(existing + needed))
        new_block = "from " + module + " import (\n    " + ",\n    ".join(merged) + ",\n)"
        return text[:match.start()] + new_block + text[match.end():]

    lines = text.splitlines()
    insert_at = 0
    while insert_at < len(lines) and (
        lines[insert_at].startswith("from __future__")
        or lines[insert_at].strip() == ""
    ):
        insert_at += 1

    block = "from " + module + " import (\n    " + ",\n    ".join(sorted(set(needed))) + ",\n)"
    lines.insert(insert_at, block)
    return "\n".join(lines) + "\n"

for path in targets:
    text = path.read_text(encoding="utf-8")
    text = remove_names_from_import_block(text, bad_module, constant_names)
    text = add_good_import(text, good_module, constant_names)
    path.write_text(text, encoding="utf-8")
    print(f"fixed {path.name}")

print("fixed wrong common imports")
