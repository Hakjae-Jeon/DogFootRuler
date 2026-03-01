from __future__ import annotations

from pathlib import Path

import pytest
import subprocess

from dogfoot.project.manager import ProjectManager


def write_system_config(base_dir: Path) -> Path:
    config_dir = base_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    system_path = config_dir / "system.yaml"
    system_path.write_text(
        "\n".join(
            [
                f"project_base_root: {base_dir / 'projects'}",
                "active_project:",
                "system_forbidden_subpaths:",
                "  - cache",
                "hard_deny_subpaths:",
                "  - .git",
                "  - secrets",
                "  - .env",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return system_path


def test_create_project_and_select_active_project(tmp_path: Path) -> None:
    manager = ProjectManager.load(write_system_config(tmp_path))
    project = manager.create_project("alpha", template="python")

    assert project.project_root == (tmp_path / "projects" / "alpha").resolve()
    assert (project.project_root / "config" / "project.yaml").exists()
    assert (project.project_root / "src" / "main.py").exists()
    assert (project.project_root / ".gitignore").read_text(encoding="utf-8").find("runs/") >= 0
    assert (project.project_root / ".git").is_dir()
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=project.project_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert branch == "main"

    manager.set_active_project("alpha")
    active = manager.get_active_project()

    assert active.name == "alpha"
    assert manager.system_config.active_project == "alpha"


def test_list_projects_only_returns_configured_projects(tmp_path: Path) -> None:
    manager = ProjectManager.load(write_system_config(tmp_path))
    manager.create_project("alpha")
    (manager.project_base_root / "scratch").mkdir(parents=True)

    assert manager.list_projects() == ["alpha"]


def test_get_project_backfills_gitignore_rules(tmp_path: Path) -> None:
    manager = ProjectManager.load(write_system_config(tmp_path))
    project = manager.create_project("alpha")
    ignore_path = project.project_root / ".gitignore"
    ignore_path.unlink()

    reloaded = manager.get_project("alpha")

    assert reloaded.project_root == project.project_root
    assert "runs/" in ignore_path.read_text(encoding="utf-8")


def test_system_forbidden_subpaths_apply_to_loaded_project(tmp_path: Path) -> None:
    manager = ProjectManager.load(write_system_config(tmp_path))
    project = manager.create_project("alpha")
    assert project.is_path_allowed("src/app.py")
    assert not project.is_path_allowed("cache/data.json")


def test_invalid_project_names_are_rejected(tmp_path: Path) -> None:
    manager = ProjectManager.load(write_system_config(tmp_path))
    with pytest.raises(ValueError):
        manager.create_project("../escape")


def test_clone_project_from_local_repo(tmp_path: Path) -> None:
    manager = ProjectManager.load(write_system_config(tmp_path))
    remote_root = tmp_path / "remote-src"
    remote_root.mkdir(parents=True, exist_ok=True)
    (remote_root / "README.md").write_text("# remote\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main"], cwd=remote_root, capture_output=True, text=True, check=True)
    subprocess.run(
        ["git", "config", "user.name", "DogFootRuler Test"],
        cwd=remote_root,
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "dogfoot@example.com"],
        cwd=remote_root,
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=remote_root, capture_output=True, text=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=remote_root, capture_output=True, text=True, check=True)

    project = manager.clone_project("alpha", str(remote_root))

    assert (project.project_root / "README.md").exists()
    assert (project.project_root / "config" / "project.yaml").exists()
    assert (project.project_root / "runs").is_dir()
