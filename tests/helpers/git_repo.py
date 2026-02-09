from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Iterator, Mapping


def _git(repo_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )


def initialize_git_repo(repo_path: Path) -> None:
    _git(repo_path, "init")
    _git(repo_path, "config", "user.email", "test@example.com")
    _git(repo_path, "config", "user.name", "Test User")


def write_repo_files(repo_path: Path, files: Mapping[str, str]) -> None:
    for relative_path, content in files.items():
        file_path = repo_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")


def commit_all(repo_path: Path, *, message: str) -> str:
    _git(repo_path, "add", ".")
    _git(repo_path, "commit", "-m", message)
    return _git(repo_path, "rev-parse", "HEAD").stdout.strip()


@contextmanager
def temporary_git_repo(
    files: Mapping[str, str],
    *,
    prefix: str = "test_repo_",
    message: str = "Initial commit",
) -> Iterator[tuple[str, str]]:
    repo_dir = tempfile.mkdtemp(prefix=prefix)
    repo_path = Path(repo_dir)
    try:
        initialize_git_repo(repo_path)
        write_repo_files(repo_path, files)
        commit_hash = commit_all(repo_path, message=message)
        yield repo_dir, commit_hash
    finally:
        shutil.rmtree(repo_dir, ignore_errors=True)
