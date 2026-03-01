from __future__ import annotations

from pathlib import Path

import pytest
import subprocess

from dogfoot.interfaces.cli import main
from dogfoot.project.manager import ProjectManager
from tests.test_manager import write_system_config


def test_cli_project_create_and_list(tmp_path: Path, capsys) -> None:
    system_config = write_system_config(tmp_path)

    exit_code = main(["--system-config", str(system_config), "project", "create", "alpha", "--template", "python"])
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "created alpha" in output
    assert (tmp_path / "projects" / "alpha" / ".gitignore").read_text(encoding="utf-8").find("runs/") >= 0
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=tmp_path / "projects" / "alpha",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert branch == "main"

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


def test_cli_fails_when_system_config_missing(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--system-config", str(tmp_path / "missing.yaml"), "project", "list"])
    assert exc.value.code == 2


def test_cli_fails_when_project_base_root_is_file(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    base_root = tmp_path / "projects-file"
    base_root.write_text("not a dir", encoding="utf-8")
    system_config = config_dir / "system.yaml"
    system_config.write_text(
        "\n".join(
            [
                f"project_base_root: {base_root}",
                "active_project:",
                "system_forbidden_subpaths:",
                "hard_deny_subpaths:",
                "  - .git",
                "",
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as exc:
        main(["--system-config", str(system_config), "project", "list"])
    assert exc.value.code == 2
