from pathlib import Path

base = Path(r"C:\Users\twone\Desktop\E_YAY CODEX\backend\app\services")

patches = {
    "snapshot_replay_source_quality_completeness.py": [
        "SnapshotRawPayloadReferenceCompleteness",
        "SnapshotSourceRecordCompleteness",
    ],
    "snapshot_replay_source_quality_drift.py": [
        "SnapshotSourceObservationSummaryDrift",
    ],
    "snapshot_replay_source_quality_reconciliation.py": [
        "SnapshotSourceDecisionUsageConsistency",
        "SnapshotSourceDecisionUsageConsistencyEntry",
        "SnapshotSourceObservationRecordSummaryReconciliation",
        "SnapshotSourceObservationRecordSummaryReconciliationEntry",
    ],
}

def add_models_import(path: Path, names: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    header = "\n".join(text.splitlines()[:120])
    missing = [name for name in names if name not in header]

    if not missing:
        print(f"already ok {path.name}")
        return

    block = "from app.services.snapshot_replay_models import (\n    " + ",\n    ".join(missing) + ",\n)"

    lines = text.splitlines()
    insert_at = 0
    while insert_at < len(lines) and (
        lines[insert_at].startswith("from __future__")
        or lines[insert_at].strip() == ""
    ):
        insert_at += 1

    lines.insert(insert_at, block)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"patched {path.name}: {', '.join(missing)}")

for filename, names in patches.items():
    add_models_import(base / filename, names)

print("result class import patch done")
