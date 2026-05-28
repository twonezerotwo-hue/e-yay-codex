from pathlib import Path
import ast
import re

base = Path(r"C:\Users\twone\Desktop\E_YAY CODEX\backend\app\services")

def exported_names(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    names = set()

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)

        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)

        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)

        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                names.add(alias.asname or alias.name)

        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])

    return {name for name in names if not name.startswith("_")}

def used_names(file_path: Path) -> set[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }

def replace_star_import(file_name: str, module_import: str, module_file: str):
    p = base / file_name
    text = p.read_text(encoding="utf-8")

    old = f"from {module_import} import *"
    if old not in text:
        return

    exports = exported_names(base / module_file)
    used = used_names(p)
    needed = sorted(exports & used)

    if not needed:
        raise RuntimeError(f"No explicit imports detected for {file_name}")

    if len(needed) <= 6:
        new = f"from {module_import} import " + ", ".join(needed)
    else:
        joined = ",\n    ".join(needed)
        new = f"from {module_import} import (\n    {joined},\n)"

    text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")
    print(f"fixed {file_name}: {len(needed)} imports")

source_common_import = "app.services.snapshot_replay_source_common"
quality_common_import = "app.services.snapshot_replay_source_quality_common"

for file_name in [
    "snapshot_replay_source_diagnostics.py",
    "snapshot_replay_source_recurrence.py",
    "snapshot_replay_source_registry.py",
    "snapshot_replay_source_timing.py",
    "snapshot_replay_source_quality_common.py",
]:
    replace_star_import(
        file_name,
        source_common_import,
        "snapshot_replay_source_common.py",
    )

for file_name in [
    "snapshot_replay_source_quality_completeness.py",
    "snapshot_replay_source_quality_drift.py",
    "snapshot_replay_source_quality_reconciliation.py",
]:
    replace_star_import(
        file_name,
        quality_common_import,
        "snapshot_replay_source_quality_common.py",
    )

print("done")
