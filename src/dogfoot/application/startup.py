from __future__ import annotations

from pathlib import Path

from dogfoot.project.manager import ProjectManager


def validate_system_config_path(system_config_path: Path) -> Path:
    resolved = system_config_path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"system config not found: {resolved}")
    return resolved


def validate_manager_startup(
    manager: ProjectManager,
    require_active_project: bool = False,
) -> None:
    base_root = manager.project_base_root
    if not base_root.exists():
        raise FileNotFoundError(f"project_base_root does not exist: {base_root}")
    if not base_root.is_dir():
        raise NotADirectoryError(f"project_base_root is not a directory: {base_root}")

    manager.recover_active_project()

    if not require_active_project:
        return

    active_name = manager.system_config.active_project
    if not active_name:
        raise ValueError("active_project is not configured")

    project = manager.get_active_project()
    project.validate_startup()
