from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from dogfoot.integrations.git_client import GitClient
from dogfoot.project.policy import PolicyViolation
from dogfoot.project.project import Project
from dogfoot.tasks.models import Status
from dogfoot.tasks.store import TaskStore
from tests.test_manager import write_system_config
from dogfoot.project.manager import ProjectManager


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)


def _init_git_repo(project_root: Path) -> None:
    if (project_root / ".git").exists():
        return
    _run(["git", "init", "-b", "main"], cwd=project_root)
    _run(["git", "config", "user.name", "DogFootRuler Test"], cwd=project_root)
    _run(["git", "config", "user.email", "dogfoot@example.com"], cwd=project_root)
    _run(["git", "add", "-A"], cwd=project_root)
    _run(["git", "commit", "-m", "Initial commit"], cwd=project_root)


def _commit_changed_file(project_root: Path, branch: str, relative_path: str, content: str) -> None:
    _run(["git", "checkout", branch], cwd=project_root)
    target = project_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _run(["git", "add", relative_path], cwd=project_root)
    _run(["git", "commit", "-m", f"Update {relative_path}"], cwd=project_root)


def _commit_all(project_root: Path, message: str) -> None:
    _run(["git", "add", "-A"], cwd=project_root)
    _run(["git", "commit", "-m", message], cwd=project_root)


@pytest.mark.integration
def test_git_diff_and_changed_files_match_project_policy(tmp_path: Path) -> None:
    manager = ProjectManager.load(write_system_config(tmp_path))
    project = manager.create_project("alpha", template="python")
    _init_git_repo(project.project_root)

    git_client = GitClient()
    branch = git_client.ensure_task_branch("task-001", project.project_root)
    _commit_changed_file(project.project_root, branch, "src/main.py", "print('updated')\n")

    diff_text = git_client.generate_diff(branch, project.project_root)
    changed_files = git_client.changed_files(branch, project.project_root)

    assert "src/main.py" in diff_text
    assert changed_files == ["src/main.py"]
    project.assert_changes_allowed(changed_files)


@pytest.mark.integration
def test_policy_violation_is_detected_from_branch_diff(tmp_path: Path) -> None:
    manager = ProjectManager.load(write_system_config(tmp_path))
    project = manager.create_project("alpha", template="python")
    project.config["allowed_subpaths"] = ["src"]
    project.save_config()
    project = Project.load(
        project.project_root,
        system_forbidden_subpaths=manager.system_config.system_forbidden_subpaths,
        hard_deny_subpaths=manager.system_config.hard_deny_subpaths,
    )
    _init_git_repo(project.project_root)
    _commit_all(project.project_root, "Update project policy")

    git_client = GitClient()
    branch = git_client.ensure_task_branch("task-002", project.project_root)
    _commit_changed_file(project.project_root, branch, "README.md", "# changed outside src\n")

    changed_files = git_client.changed_files(branch, project.project_root)

    assert changed_files == ["README.md"]
    with pytest.raises(PolicyViolation):
        project.assert_changes_allowed(changed_files)


@pytest.mark.integration
def test_task_store_creates_project_scoped_run_archive(tmp_path: Path) -> None:
    manager = ProjectManager.load(write_system_config(tmp_path))
    project = manager.create_project("alpha", template="python")
    store = TaskStore(manager=manager, legacy_runs_dir=tmp_path / "legacy-runs")

    task_id = store.create_task(user_id=1, chat_id=2, text="say hi", project=project)
    task_dir = store.resolve_task_dir(task_id)
    meta = store.load_task_meta(task_id)

    assert task_dir == project.project_root / "runs" / task_id
    assert (task_dir / "request.txt").read_text(encoding="utf-8") == "say hi"
    assert meta["project_name"] == "alpha"
    assert meta["project_root"] == str(project.project_root)
    assert meta["status"] == Status.QUEUED
