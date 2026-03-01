from __future__ import annotations

from pathlib import Path

import pytest

from dogfoot.project.policy import PathPolicy, PolicyViolation


def make_policy(tmp_path: Path, **kwargs: object) -> PathPolicy:
    root = tmp_path / "project"
    root.mkdir()
    return PathPolicy.from_config(project_root=root, **kwargs)


def test_denies_project_root_escape_with_parent_segments(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    assert not policy.is_path_allowed("../outside.txt")


def test_denies_absolute_paths(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    assert not policy.is_path_allowed("/tmp/outside.txt")


def test_denies_hard_deny_paths_even_inside_root(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    assert not policy.is_path_allowed(".git/config")
    assert not policy.is_path_allowed("secrets/token.txt")
    assert not policy.is_path_allowed(".env")


def test_denies_forbidden_subpaths(tmp_path: Path) -> None:
    policy = make_policy(tmp_path, forbidden_subpaths=["internal", "build/output.txt"])
    assert not policy.is_path_allowed("internal/module.py")
    assert not policy.is_path_allowed("build/output.txt")
    assert policy.is_path_allowed("src/module.py")


def test_allowed_subpaths_enable_lock_mode(tmp_path: Path) -> None:
    policy = make_policy(tmp_path, allowed_subpaths=["src", "README.md"])
    assert policy.is_path_allowed("src/app.py")
    assert policy.is_path_allowed("README.md")
    assert not policy.is_path_allowed("docs/notes.md")


def test_symlink_escape_is_blocked(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = project_root / "linked"
    link.symlink_to(outside, target_is_directory=True)
    policy = PathPolicy.from_config(project_root=project_root)
    assert not policy.is_path_allowed("linked/secrets.txt")


def test_assert_changes_allowed_raises_for_disallowed_change(tmp_path: Path) -> None:
    policy = make_policy(tmp_path, allowed_subpaths=["src"])
    with pytest.raises(PolicyViolation):
        policy.assert_changes_allowed(["src/app.py", "README.md"])


def test_assert_changes_allowed_rejects_empty_change_list(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    with pytest.raises(PolicyViolation):
        policy.assert_changes_allowed([])


def test_normalize_change_paths_deduplicates_and_normalizes(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    normalized = policy.normalize_change_paths(["src//app.py", "./src/app.py", "src/app.py"])
    assert normalized == ["src/app.py"]
