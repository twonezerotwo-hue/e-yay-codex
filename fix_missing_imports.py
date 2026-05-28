from pathlib import Path

base = Path(r"C:\Users\twone\Desktop\E_YAY CODEX\backend\app\services")

patches = {
    "snapshot_replay_source_quality_completeness.py": "from collections import Counter\nfrom datetime import UTC, datetime\n",
    "snapshot_replay_source_quality_drift.py": "from datetime import UTC, datetime\n",
    "snapshot_replay_source_quality_reconciliation.py": "from collections import Counter\nfrom datetime import UTC, datetime\n",
}

for filename, needed_imports in patches.items():
    path = base / filename
    text = path.read_text(encoding="utf-8")

    lines = text.splitlines()
    insert_at = 0

    while insert_at < len(lines) and (
        lines[insert_at].startswith("from __future__")
        or lines[insert_at].strip() == ""
    ):
        insert_at += 1

    for import_line in reversed(needed_imports.strip().splitlines()):
        if import_line not in text:
            lines.insert(insert_at, import_line)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"patched {filename}")

print("done")
