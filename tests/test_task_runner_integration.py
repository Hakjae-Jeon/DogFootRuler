from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

import pytest

from dogfoot.application.task_runner import TaskRunner
from dogfoot.integrations.git_client import GitClient
from dogfoot.project.manager import ProjectManager
from dogfoot.project.project import Project
from dogfoot.tasks.models import Status
from dogfoot.tasks.store import TaskStore
from tests.test_manager import write_system_config


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)


def _init_git_repo(project_root: Path) -> None:
    _run(["git", "init", "-b", "main"], cwd=project_root)
    _run(["git", "config", "user.name", "DogFootRuler Test"], cwd=project_root)
    _run(["git", "config", "user.email", "dogfoot@example.com"], cwd=project_root)
    _run(["git", "add", "-A"], cwd=project_root)
    _run(["git", "commit", "-m", "Initial commit"], cwd=project_root)


class FakeCodexRunner:
    def __init__(self, action):
        self.action = action

    def run(self, task_id: str, prompt: str, project_root: Path) -> tuple[int, str, str, str]:
        return self.action(task_id, prompt, project_root)


async def _notifier(task_id: str, text: str) -> None:
    _notifier.messages.append((task_id, text))


_notifier.messages = []


def _load_project(manager: ProjectManager, project_root: Path) -> Project:
    return Project.load(
        project_root,
        system_forbidden_subpaths=manager.system_config.system_forbidden_subpaths,
        hard_deny_subpaths=manager.system_config.hard_deny_subpaths,
    )


def _make_runner(
    manager: ProjectManager,
    store: TaskStore,
    codex_runner: FakeCodexRunner,
) -> TaskRunner:
    return TaskRunner(
        task_store=store,
        git_client=GitClient(),
        codex_runner=codex_runner,
        project_loader=lambda meta: _load_project(manager, Path(str(meta["project_root"]))),
        notifier=_notifier,
        logger=logging.getLogger("test-task-runner"),
    )


@pytest.mark.integration
def test_task_runner_success_creates_summary_diff_and_ready_state(tmp_path: Path) -> None:
    manager = ProjectManager.load(write_system_config(tmp_path))
    project = manager.create_project("alpha", template="python")
    _init_git_repo(project.project_root)
    store = TaskStore(manager=manager, legacy_runs_dir=tmp_path / "legacy-runs")

    def action(task_id: str, prompt: str, project_root: Path) -> tuple[int, str, str, str]:
        target = project_root / "src" / "main.py"
        target.write_text("print('from fake codex')\n", encoding="utf-8")
        return 0, "token=abc123\nok", "", ""

    runner = _make_runner(manager, store, FakeCodexRunner(action))
    _notifier.messages.clear()
    task_id = store.create_task(user_id=1, chat_id=2, text="update main", project=project)

    asyncio.run(runner.process_task(task_id))

    meta = store.load_task_meta(task_id)
    task_dir = store.resolve_task_dir(task_id)
    assert meta["status"] == Status.READY_TO_APPLY
    assert meta["changed_files"] == ["src/main.py"]
    assert (task_dir / "diff.patch").exists()
    assert (task_dir / "summary.md").read_text(encoding="utf-8").find("프로젝트: alpha") >= 0
    assert (task_dir / "stdout.log").read_text(encoding="utf-8").find("token***") >= 0
    assert _notifier.messages and _notifier.messages[-1][0] == task_id


@pytest.mark.integration
def test_task_runner_policy_violation_marks_failed(tmp_path: Path) -> None:
    manager = ProjectManager.load(write_system_config(tmp_path))
    project = manager.create_project("alpha", template="python")
    project.config["allowed_subpaths"] = ["src"]
    project.save_config()
    project = _load_project(manager, project.project_root)
    _init_git_repo(project.project_root)
    store = TaskStore(manager=manager, legacy_runs_dir=tmp_path / "legacy-runs")

    def action(task_id: str, prompt: str, project_root: Path) -> tuple[int, str, str, str]:
        (project_root / "README.md").write_text("# invalid change\n", encoding="utf-8")
        return 0, "", "", ""

    runner = _make_runner(manager, store, FakeCodexRunner(action))
    _notifier.messages.clear()
    task_id = store.create_task(user_id=1, chat_id=2, text="break policy", project=project)

    asyncio.run(runner.process_task(task_id))

    meta = store.load_task_meta(task_id)
    task_dir = store.resolve_task_dir(task_id)
    assert meta["status"] == Status.FAILED
    assert meta["changed_files"] == ["README.md"]
    assert "Change is not allowed" in str(meta["notes"])
    assert (task_dir / "summary.md").read_text(encoding="utf-8").find("정책 위반") >= 0


@pytest.mark.integration
def test_task_runner_honors_canceled_status_after_codex_run(tmp_path: Path) -> None:
    manager = ProjectManager.load(write_system_config(tmp_path))
    project = manager.create_project("alpha", template="python")
    _init_git_repo(project.project_root)
    store = TaskStore(manager=manager, legacy_runs_dir=tmp_path / "legacy-runs")
    task_id = store.create_task(user_id=1, chat_id=2, text="cancel me", project=project)

    def action(current_task_id: str, prompt: str, project_root: Path) -> tuple[int, str, str, str]:
        store.update_meta(
            current_task_id,
            status=Status.CANCELED,
            notes="사용자 취소(실행 중)",
        )
        (project_root / "src" / "main.py").write_text("print('canceled')\n", encoding="utf-8")
        return 0, "", "", "cancelled"

    runner = _make_runner(manager, store, FakeCodexRunner(action))
    _notifier.messages.clear()

    asyncio.run(runner.process_task(task_id))

    meta = store.load_task_meta(task_id)
    task_dir = store.resolve_task_dir(task_id)
    assert meta["status"] == Status.CANCELED
    assert meta["notes"] == "사용자 취소"
    assert (task_dir / "summary.md").read_text(encoding="utf-8").find("사용자 취소") >= 0
