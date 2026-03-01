from __future__ import annotations

from pathlib import Path

from dogfoot.interfaces.cli import main
from dogfoot.project.manager import ProjectManager
from tests.test_manager import write_system_config


def test_cli_project_create_and_list(tmp_path: Path, capsys) -> None:
    system_config = write_system_config(tmp_path)

    exit_code = main(["--system-config", str(system_config), "project", "create", "alpha", "--template", "python"])
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "created alpha" in output

    exit_code = main(["--system-config", str(system_config), "project", "list"])
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "alpha" in output


def test_cli_project_use_updates_active_project(tmp_path: Path, capsys) -> None:
    system_config = write_system_config(tmp_path)
    manager = ProjectManager.load(system_config)
    manager.create_project("alpha")

    exit_code = main(["--system-config", str(system_config), "project", "use", "alpha"])
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "active project set to alpha" in output

    manager = ProjectManager.load(system_config)
    assert manager.system_config.active_project == "alpha"
