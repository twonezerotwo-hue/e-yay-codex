from pathlib import Path
import ast
import re

base = Path(r"C:\Users\twone\Desktop\E_YAY CODEX\backend\app\services")

modules = {
    "app.services.snapshot_replay_source_common": base / "snapshot_replay_source_common.py",
    "app.services.snapshot_replay_source_quality_common": base / "snapshot_replay_source_quality_common.py",
    "app.services.snapshot_replay_models": base / "snapshot_replay_models.py",
}

targets = [
    base / "snapshot_replay_source_quality_drift.py",
    base / "snapshot_replay_source_quality_reconciliation.py",
]

wanted = [
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

def exported(path: Path) -> set[str]:
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
    return names

exports = {module: exported(path) for module, path in modules.items()}

def remove_name_from_all_imports(text: str, name: str) -> str:
    pattern = re.compile(r"from (?P<module>[\w\.]+) import \(\n(?P<body>.*?)\n\)", re.DOTALL)

    def repl(match):
        module = match.group("module")
        body = match.group("body")
        names = []
        for line in body.splitlines():
            item = line.strip().rstrip(",")
            if item and item != name:
                names.append(item)
        if not names:
            return ""
        return f"from {module} import (\n    " + ",\n    ".join(sorted(set(names))) + ",\n)"

    return pattern.sub(repl, text)

def add_import(text: str, module: str, names: list[str]) -> str:
    names = sorted(set(names))
    if not names:
        return text

    pattern = re.compile(rf"from {re.escape(module)} import \(\n(?P<body>.*?)\n\)", re.DOTALL)
    match = pattern.search(text)

    if match:
        existing = []
        for line in match.group("body").splitlines():
            item = line.strip().rstrip(",")
            if item:
                existing.append(item)
        merged = sorted(set(existing + names))
        block = f"from {module} import (\n    " + ",\n    ".join(merged) + ",\n)"
        return text[:match.start()] + block + text[match.end():]

    lines = text.splitlines()
    insert_at = 0
    while insert_at < len(lines) and (
        lines[insert_at].startswith("from __future__")
        or lines[insert_at].strip() == ""
    ):
        insert_at += 1

    block = f"from {module} import (\n    " + ",\n    ".join(names) + ",\n)"
    lines.insert(insert_at, block)
    return "\n".join(lines) + "\n"

for path in targets:
    text = path.read_text(encoding="utf-8")

    for name in wanted:
        text = remove_name_from_all_imports(text, name)

    add_by_module = {}
    for name in wanted:
        if name not in text:
            continue
        for module, names in exports.items():
            if name in names:
                add_by_module.setdefault(module, []).append(name)
                break

    for module, names in add_by_module.items():
        text = add_import(text, module, names)

    path.write_text(text, encoding="utf-8")
    print(f"fixed imports in {path.name}")

print("import source repair done")
