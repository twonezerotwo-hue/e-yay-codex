from pathlib import Path
import ast
import builtins

base = Path(r"C:\Users\twone\Desktop\E_YAY CODEX\backend\app\services")

SOURCE_MODULES = {
    "app.services.snapshot_replay_models": base / "snapshot_replay_models.py",
    "app.services.snapshot_replay_source_common": base / "snapshot_replay_source_common.py",
    "app.services.snapshot_replay_source_quality_common": base / "snapshot_replay_source_quality_common.py",
}

TARGETS = [
    base / "snapshot_replay_source_quality_completeness.py",
    base / "snapshot_replay_source_quality_drift.py",
    base / "snapshot_replay_source_quality_reconciliation.py",
]

BUILTINS = set(dir(builtins)) | {
    "Any", "Mapping", "Counter", "UTC", "datetime",
    "list", "tuple", "dict", "set", "str", "int", "float", "bool", "None",
}

def exported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
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
                if alias.name != "*":
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return {n for n in names if not n.startswith("_")}

def imported_and_defined_names(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
            for arg in node.args.args + node.args.kwonlyargs:
                names.add(arg.arg)
            if node.args.vararg:
                names.add(node.args.vararg.arg)
            if node.args.kwarg:
                names.add(node.args.kwarg.arg)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
            elif isinstance(node.target, tuple):
                for item in node.target.elts:
                    if isinstance(item, ast.Name):
                        names.add(item.id)
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                names.add(node.name)
    return names

def used_names(tree: ast.AST) -> set[str]:
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

exports_by_module = {
    module: exported_names(path)
    for module, path in SOURCE_MODULES.items()
}

for target in TARGETS:
    text = target.read_text(encoding="utf-8")
    tree = ast.parse(text)
    used = used_names(tree)
    defined = imported_and_defined_names(tree)
    missing = sorted((used - defined) - BUILTINS)

    imports_to_add = {}

    for name in missing:
        for module, exports in exports_by_module.items():
            if name in exports:
                imports_to_add.setdefault(module, []).append(name)
                break

    if not imports_to_add:
        print(f"already ok {target.name}")
        continue

    lines = text.splitlines()
    insert_at = 0
    while insert_at < len(lines) and (
        lines[insert_at].startswith("from __future__")
        or lines[insert_at].strip() == ""
    ):
        insert_at += 1

    new_import_lines = []
    for module, names in sorted(imports_to_add.items()):
        names = sorted(set(names))
        if len(names) <= 5:
            new_import_lines.append(f"from {module} import " + ", ".join(names))
        else:
            joined = ",\n    ".join(names)
            new_import_lines.append(f"from {module} import (\n    {joined},\n)")

    lines[insert_at:insert_at] = new_import_lines + [""]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"patched {target.name}: {sum(len(v) for v in imports_to_add.values())} imports")

print("auto import repair done")
