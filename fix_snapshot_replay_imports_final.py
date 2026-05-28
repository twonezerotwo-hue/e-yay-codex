from pathlib import Path
import ast

base = Path(r"C:\Users\twone\Desktop\E_YAY CODEX\backend\app\services")
models_path = base / "snapshot_replay_models.py"

tree = ast.parse(models_path.read_text(encoding="utf-8"))

model_names = []
for node in tree.body:
    if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
        if node.name.startswith("SnapshotSourceDiagnostics"):
            model_names.append(node.name)

model_names = sorted(set(model_names))

common_names = [
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

def add_import_block(path: Path, module: str, names: list[str]) -> None:
    text = path.read_text(encoding="utf-8")

    needed = [name for name in names if name in text and name not in text.split("\n", 40)[0:40]]
    if not needed:
        return

    import_block = "from " + module + " import (\n    " + ",\n    ".join(sorted(set(needed))) + ",\n)\n"

    if import_block in text:
        return

    lines = text.splitlines()
    insert_at = 0
    while insert_at < len(lines) and (
        lines[insert_at].startswith("from __future__")
        or lines[insert_at].strip() == ""
    ):
        insert_at += 1

    lines.insert(insert_at, import_block.rstrip())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"patched {path.name}")

for target in targets:
    add_import_block(target, "app.services.snapshot_replay_models", model_names)
    add_import_block(target, "app.services.snapshot_replay_source_quality_common", common_names)

print("patch done")
