from __future__ import annotations

from pathlib import Path

import pytest

from dogfoot.application.startup import validate_manager_startup, validate_system_config_path
from dogfoot.project.manager import ProjectManager
from tests.test_manager import write_system_config


def test_validate_system_config_path_requires_existing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        validate_system_config_path(tmp_path / "missing.yaml")


def test_validate_manager_startup_requires_active_project_when_requested(tmp_path: Path) -> None:
    manager = ProjectManager.load(write_system_config(tmp_path))
    with pytest.raises(ValueError):
        validate_manager_startup(manager, require_active_project=True)


def test_validate_manager_startup_validates_active_project_runs_dir(tmp_path: Path) -> None:
    manager = ProjectManager.load(write_system_config(tmp_path))
    project = manager.create_project("alpha")
    manager.set_active_project("alpha")
    runs_dir = project.project_root / "runs"
    runs_dir.rmdir()
    runs_dir.write_text("not a dir", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        validate_manager_startup(manager, require_active_project=True)
