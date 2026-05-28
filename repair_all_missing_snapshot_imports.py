from pathlib import Path
import ast
import builtins
import re

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
    base / "snapshot_replay_source_quality.py",
    base / "snapshot_replay_source_diagnostics.py",
]

BUILTINS = set(dir(builtins)) | {
    "Any", "Mapping", "Counter", "UTC", "datetime",
    "list", "tuple", "dict", "set", "str", "int", "float", "bool", "None",
    "Exception", "ValueError", "TypeError", "len", "sum", "min", "max", "round",
    "sorted", "tuple", "dict", "set", "isinstance", "range", "enumerate",
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

def defined_names(tree: ast.AST) -> set[str]:
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
            targets = [node.target]
            while targets:
                target = targets.pop()
                if isinstance(target, ast.Name):
                    names.add(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    targets.extend(target.elts)
        elif isinstance(node, ast.With):
            for item in node.items:
                if isinstance(item.optional_vars, ast.Name):
                    names.add(item.optional_vars.id)
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                names.add(node.name)
        elif isinstance(node, ast.comprehension):
            target = node.target
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        names.add(elt.id)
    return names

def used_names(tree: ast.AST) -> set[str]:
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

def existing_import_block_modules(text: str) -> set[str]:
    return set(re.findall(r"^from ([\w\.]+) import", text, flags=re.MULTILINE))

exports_by_module = {
    module: exported_names(path)
    for module, path in SOURCE_MODULES.items()
}

for target in TARGETS:
    if not target.exists():
        continue

    text = target.read_text(encoding="utf-8")
    tree = ast.parse(text)

    used = used_names(tree)
    defined = defined_names(tree)
    missing = sorted((used - defined) - BUILTINS)

    imports_to_add: dict[str, list[str]] = {}

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

    new_imports = []
    for module, names in sorted(imports_to_add.items()):
        names = sorted(set(names))
        if len(names) <= 4:
            new_imports.append(f"from {module} import " + ", ".join(names))
        else:
            joined = ",\n    ".join(names)
            new_imports.append(f"from {module} import (\n    {joined},\n)")

    lines[insert_at:insert_at] = new_imports + [""]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"patched {target.name}: {sum(len(v) for v in imports_to_add.values())} imports")

print("missing import repair done")
