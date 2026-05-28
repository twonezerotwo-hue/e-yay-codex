from pathlib import Path

base = Path(r"C:\Users\twone\Desktop\E_YAY CODEX\backend\app\services")

files = [
    "snapshot_replay_source_quality_drift.py",
    "snapshot_replay_source_quality_reconciliation.py",
]

for filename in files:
    path = base / filename
    text = path.read_text(encoding="utf-8")

    import_line = "from collections.abc import Mapping"

    if import_line not in text:
        lines = text.splitlines()
        insert_at = 0

        while insert_at < len(lines) and (
            lines[insert_at].startswith("from __future__")
            or lines[insert_at].strip() == ""
        ):
            insert_at += 1

        lines.insert(insert_at, import_line)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"patched {filename}")
    else:
        print(f"already patched {filename}")

print("done")
