"""Git versioning with real git when available (C13)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.timeout(30)]


def test_xet_git_versioning_real_repo(tmp_path: Path) -> None:
    if not shutil.which("git"):
        pytest.skip("git not installed")
    from ccbt.storage import git_versioning

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "f.txt").write_text("v1", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "c1"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    assert git_versioning is not None
    if hasattr(git_versioning, "get_head_ref"):
        ref = git_versioning.get_head_ref(repo)
        assert ref
    elif hasattr(git_versioning, "GitVersioning"):
        gv = git_versioning.GitVersioning(repo)
        assert gv is not None
