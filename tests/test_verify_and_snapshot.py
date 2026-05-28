from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.verify_and_snapshot import CommandResult
from scripts.verify_and_snapshot import VerificationError
from scripts.verify_and_snapshot import iter_backup_files
from scripts.verify_and_snapshot import verify_backend_tests
from scripts.verify_and_snapshot import verify_and_snapshot


FIXED_TIMESTAMP = datetime(2026, 5, 18, 12, 30, 45, tzinfo=UTC)


def create_repo_fixture(repo_root: Path) -> None:
    (repo_root / "backend").mkdir(parents=True, exist_ok=True)
    (repo_root / "clean_backups").mkdir(parents=True, exist_ok=True)
    (repo_root / "backend" / "app").mkdir(parents=True, exist_ok=True)
    (repo_root / "backend" / "app" / "main.py").write_text("print('ok')", encoding="utf-8")
    (repo_root / "backend" / ".env.example").write_text("POSTGRES_PASSWORD=change_me", encoding="utf-8")
    (repo_root / "docker-compose.yml").write_text("services: {}", encoding="utf-8")
    (repo_root / "README.md").write_text("repo", encoding="utf-8")


def successful_runner(command: list[str], cwd: Path) -> CommandResult:
    return CommandResult(returncode=0, stdout="ok", stderr="")


def test_verify_backend_tests_uses_clean_repo_local_temp_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = tmp_path / "repo"
    create_repo_fixture(repo_root)

    stale_run_root = repo_root / ".snapshot_tmp" / "verify_run_stale"
    stale_base_temp_file = stale_run_root / "pytest_basetemp" / "stale.txt"
    stale_base_temp_file.parent.mkdir(parents=True, exist_ok=True)
    stale_base_temp_file.write_text("stale", encoding="utf-8")

    stale_system_temp_file = stale_run_root / "system_temp" / "stale.txt"
    stale_system_temp_file.parent.mkdir(parents=True, exist_ok=True)
    stale_system_temp_file.write_text("stale", encoding="utf-8")

    monkeypatch.setenv("TMP", "original-tmp")
    monkeypatch.setenv("TEMP", "original-temp")
    monkeypatch.setenv("TMPDIR", "original-tmpdir")

    captured: dict[str, object] = {}

    def inspecting_runner(command: list[str], cwd: Path) -> CommandResult:
        captured["command"] = command
        captured["cwd"] = cwd
        captured["TMP"] = os.environ["TMP"]
        captured["TEMP"] = os.environ["TEMP"]
        captured["TMPDIR"] = os.environ["TMPDIR"]
        return CommandResult(returncode=0, stdout="ok", stderr="")

    verify_backend_tests(repo_root, command_runner=inspecting_runner)

    expected_system_temp_dir = Path(str(captured["TMP"]))
    expected_base_temp_dir = Path(captured["command"][6])

    assert captured["cwd"] == repo_root
    assert captured["command"][0:5] == [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
    ]
    assert captured["command"][5] == "--basetemp"
    assert captured["command"][6] == str(expected_base_temp_dir)
    assert captured["command"][7] == "-q"
    assert captured["TMP"] == str(expected_system_temp_dir)
    assert captured["TEMP"] == str(expected_system_temp_dir)
    assert captured["TMPDIR"] == str(expected_system_temp_dir)
    assert expected_system_temp_dir.parent.parent == repo_root / ".snapshot_tmp"
    assert expected_base_temp_dir.parent == expected_system_temp_dir.parent
    assert expected_system_temp_dir.name == "system_temp"
    assert expected_base_temp_dir.name == "pytest_basetemp"
    assert expected_system_temp_dir.exists()
    assert expected_base_temp_dir.exists()
    assert not stale_base_temp_file.exists()
    assert not stale_system_temp_file.exists()
    assert os.environ["TMP"] == "original-tmp"
    assert os.environ["TEMP"] == "original-temp"
    assert os.environ["TMPDIR"] == "original-tmpdir"


def test_iter_backup_files_skips_excluded_directories_without_descending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    create_repo_fixture(repo_root)
    excluded_directory = repo_root / ".snapshot_tmp"
    excluded_directory.mkdir(parents=True, exist_ok=True)
    (excluded_directory / "blocked.txt").write_text("blocked", encoding="utf-8")

    original_iterdir = Path.iterdir

    def guarded_iterdir(self: Path):
        if self == excluded_directory:
            raise AssertionError("Excluded temp directories should not be traversed.")
        return original_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)

    files = iter_backup_files(repo_root)
    archived_names = {path.relative_to(repo_root).as_posix() for path in files}

    assert "backend/app/main.py" in archived_names
    assert ".snapshot_tmp/blocked.txt" not in archived_names


def test_backup_is_not_created_when_tests_fail(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    create_repo_fixture(repo_root)
    existing_backup = repo_root / "clean_backups" / "eyay_clean_20260517T000000Z.zip"
    existing_backup.write_text("old", encoding="utf-8")

    def failing_runner(command: list[str], cwd: Path) -> CommandResult:
        return CommandResult(returncode=1, stdout="", stderr="pytest failed")

    with pytest.raises(VerificationError):
        verify_and_snapshot(repo_root, command_runner=failing_runner, now=FIXED_TIMESTAMP)

    assert existing_backup.exists()
    assert list((repo_root / "clean_backups").glob("eyay_clean_*.zip")) == [existing_backup]


def test_successful_run_creates_clean_backup(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    create_repo_fixture(repo_root)
    (repo_root / ".git").mkdir()
    (repo_root / ".git" / "config").write_text("git", encoding="utf-8")
    (repo_root / ".snapshot_tmp").mkdir()
    (repo_root / ".snapshot_tmp" / "work.tmp").write_text("scratch", encoding="utf-8")
    (repo_root / "logs").mkdir()
    (repo_root / "logs" / "app.log").write_text("log", encoding="utf-8")
    (repo_root / "local.db").write_text("db", encoding="utf-8")

    backup_path = verify_and_snapshot(repo_root, command_runner=successful_runner, now=FIXED_TIMESTAMP)

    assert backup_path.exists()
    with ZipFile(backup_path, "r") as archive:
        archived_names = set(archive.namelist())

    assert "backend/app/main.py" in archived_names
    assert "docker-compose.yml" in archived_names
    assert ".git/config" not in archived_names
    assert ".snapshot_tmp/work.tmp" not in archived_names
    assert "logs/app.log" not in archived_names
    assert "local.db" not in archived_names


def test_new_clean_backup_removes_only_previous_clean_backup(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    create_repo_fixture(repo_root)
    old_clean_backup = repo_root / "clean_backups" / "eyay_clean_20260517T000000Z.zip"
    old_clean_backup.write_text("old", encoding="utf-8")
    other_zip = repo_root / "clean_backups" / "manual_snapshot.zip"
    other_zip.write_text("manual", encoding="utf-8")

    backup_path = verify_and_snapshot(repo_root, command_runner=successful_runner, now=FIXED_TIMESTAMP)

    assert backup_path.exists()
    assert not old_clean_backup.exists()
    assert other_zip.exists()


def test_docker_validation_failure_prevents_backup_creation(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    create_repo_fixture(repo_root)

    def selective_runner(command: list[str], cwd: Path) -> CommandResult:
        if command[0].endswith("python") or command[0].endswith("python.exe"):
            return CommandResult(returncode=0, stdout="tests ok", stderr="")
        return CommandResult(returncode=1, stdout="", stderr="compose failed")

    with pytest.raises(VerificationError):
        verify_and_snapshot(repo_root, command_runner=selective_runner, now=FIXED_TIMESTAMP)

    assert list((repo_root / "clean_backups").glob("eyay_clean_*.zip")) == []
