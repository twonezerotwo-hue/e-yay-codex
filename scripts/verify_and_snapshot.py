from __future__ import annotations

import subprocess
import sys
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


CLEAN_BACKUP_PREFIX = "eyay_clean_"
SNAPSHOT_TEMP_DIR_NAME = ".snapshot_tmp"
SNAPSHOT_TEMP_RUN_PREFIX = "verify_run_"
EXCLUDED_DIR_NAMES = {
    ".codex_tmp",
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    SNAPSHOT_TEMP_DIR_NAME,
    "clean_backups",
    "logs",
    "postgres_data",
    "redis_data",
    "pgdata",
}
EXCLUDED_FILE_NAMES = {
    "dump.rdb",
    "appendonly.aof",
}
EXCLUDED_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".sqlite-journal",
}


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class VerificationError(RuntimeError):
    pass


def run_command(command: list[str], cwd: Path) -> CommandResult:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def recreate_directory(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
        if path.exists():
            raise VerificationError(f"Could not recreate temp directory: {path}")

    path.mkdir(parents=True, exist_ok=True)
    return path


def create_temp_run_root(snapshot_temp_root: Path) -> Path:
    snapshot_temp_root.mkdir(parents=True, exist_ok=True)
    run_root_name = (
        f"{SNAPSHOT_TEMP_RUN_PREFIX}"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    )
    run_root = snapshot_temp_root / run_root_name
    run_root.mkdir(parents=True, exist_ok=False)
    return run_root


def cleanup_previous_temp_runs(snapshot_temp_root: Path, *, keep_run_root: Path) -> None:
    for candidate in snapshot_temp_root.iterdir():
        if candidate == keep_run_root:
            continue
        if not candidate.is_dir():
            continue
        if not candidate.name.startswith(SNAPSHOT_TEMP_RUN_PREFIX):
            continue
        shutil.rmtree(candidate, ignore_errors=True)


def verify_backend_tests(repo_root: Path, command_runner=run_command) -> CommandResult:
    snapshot_temp_root = repo_root / SNAPSHOT_TEMP_DIR_NAME
    temp_run_root = create_temp_run_root(snapshot_temp_root)
    cleanup_previous_temp_runs(snapshot_temp_root, keep_run_root=temp_run_root)
    system_temp_dir = recreate_directory(temp_run_root / "system_temp")
    pytest_base_temp_dir = recreate_directory(temp_run_root / "pytest_basetemp")

    original_environment = {
        "TMP": os.environ.get("TMP"),
        "TEMP": os.environ.get("TEMP"),
        "TMPDIR": os.environ.get("TMPDIR"),
    }

    os.environ["TMP"] = str(system_temp_dir)
    os.environ["TEMP"] = str(system_temp_dir)
    os.environ["TMPDIR"] = str(system_temp_dir)

    try:
        result = command_runner(
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "--basetemp",
                str(pytest_base_temp_dir),
                "-q",
            ],
            repo_root,
        )
    finally:
        for key, value in original_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    if result.returncode != 0:
        raise VerificationError("Project tests failed.")
    return result


def verify_docker_compose(repo_root: Path, command_runner=run_command) -> CommandResult:
    result = command_runner(
        ["docker", "compose", "--env-file", "backend/.env.example", "config"],
        repo_root,
    )
    if result.returncode != 0:
        raise VerificationError("Docker compose config validation failed.")
    return result


def should_exclude(relative_path: Path) -> bool:
    if any(part in EXCLUDED_DIR_NAMES for part in relative_path.parts[:-1]):
        return True

    if relative_path.name in EXCLUDED_FILE_NAMES:
        return True

    if any(relative_path.name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
        return True

    return False


def should_skip_directory(relative_path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in relative_path.parts)


def iter_backup_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    directories_to_visit = [repo_root]

    while directories_to_visit:
        current_directory = directories_to_visit.pop()

        for path in sorted(current_directory.iterdir(), key=lambda item: item.name):
            relative_path = path.relative_to(repo_root)

            if path.is_dir():
                if should_skip_directory(relative_path):
                    continue

                directories_to_visit.append(path)
                continue

            if should_exclude(relative_path):
                continue

            files.append(path)

    return sorted(files)


def build_backup_name(now: datetime | None = None) -> str:
    current_time = now or datetime.now(UTC)
    timestamp = current_time.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{CLEAN_BACKUP_PREFIX}{timestamp}.zip"


def validate_zip_file(zip_path: Path) -> None:
    with ZipFile(zip_path, "r") as archive:
        names = archive.namelist()
        if not names:
            raise VerificationError("Backup archive is empty.")
        if archive.testzip() is not None:
            raise VerificationError("Backup archive validation failed.")


def cleanup_old_clean_backups(backup_dir: Path, keep_backup: Path) -> None:
    for candidate in backup_dir.glob(f"{CLEAN_BACKUP_PREFIX}*.zip"):
        if candidate != keep_backup:
            candidate.unlink()


def create_clean_backup(repo_root: Path, now: datetime | None = None) -> Path:
    backup_dir = repo_root / "clean_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    final_backup = backup_dir / build_backup_name(now=now)
    temp_backup = backup_dir / f"{final_backup.name}.tmp"

    files_to_backup = iter_backup_files(repo_root)

    with ZipFile(temp_backup, "w", compression=ZIP_DEFLATED) as archive:
        for path in files_to_backup:
            archive.write(path, path.relative_to(repo_root))

    validate_zip_file(temp_backup)
    temp_backup.replace(final_backup)
    cleanup_old_clean_backups(backup_dir, final_backup)
    return final_backup


def verify_and_snapshot(
    repo_root: Path,
    *,
    command_runner=run_command,
    now: datetime | None = None,
) -> Path:
    verify_backend_tests(repo_root, command_runner=command_runner)
    verify_docker_compose(repo_root, command_runner=command_runner)
    return create_clean_backup(repo_root, now=now)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    try:
        backup_path = verify_and_snapshot(repo_root)
    except VerificationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(str(backup_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
