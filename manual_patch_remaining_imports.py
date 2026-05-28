from pathlib import Path

base = Path(r"C:\Users\twone\Desktop\E_YAY CODEX\backend\app\services")

patches = {
    "snapshot_replay_source_quality_completeness.py": {
        "app.services.snapshot_replay_models": [
            "SnapshotRawPayloadReferenceCompletenessEntry",
            "SnapshotSourceRecordCompletenessEntry",
        ],
    },
    "snapshot_replay_source_quality_drift.py": {
        "app.services.snapshot_replay_models": [
            "SnapshotSourceObservationSummaryDriftEntry",
        ],
    },
    "snapshot_replay_source_quality_reconciliation.py": {
        "app.services.snapshot_replay_source_common": [
            "ALLOWED_DECISION_USAGES",
        ],
    },
}

def add_import(path: Path, module: str, names: list[str]) -> None:
    text = path.read_text(encoding="utf-8")

    missing = [name for name in names if name not in text.splitlines()[0:80]]
    if not missing:
        return

    import_block = "from " + module + " import (\n    " + ",\n    ".join(missing) + ",\n)\n"

    lines = text.splitlines()
    insert_at = 0

    while insert_at < len(lines) and (
        lines[insert_at].startswith("from __future__")
        or lines[insert_at].strip() == ""
    ):
        insert_at += 1

    lines.insert(insert_at, import_block.rstrip())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"patched {path.name}: {', '.join(missing)}")

for filename, module_map in patches.items():
    path = base / filename
    for module, names in module_map.items():
        add_import(path, module, names)

print("manual import patch done")
