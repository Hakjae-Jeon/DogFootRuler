from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from dogfoot.application.startup import validate_manager_startup, validate_system_config_path
from dogfoot.project.manager import ProjectManager


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SYSTEM_CONFIG = REPO_ROOT / "config" / "system.yaml"


def resolve_system_config(path_value: str | None = None) -> Path:
    if path_value:
        return Path(path_value).resolve()
    env_value = os.environ.get("DOGFOOT_SYSTEM_CONFIG")
    if env_value:
        return Path(env_value).resolve()
    return DEFAULT_SYSTEM_CONFIG


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dogfoot")
    parser.add_argument(
        "--system-config",
        default=None,
        help="Path to system.yaml. Defaults to DOGFOOT_SYSTEM_CONFIG or config/system.yaml.",
    )
    subparsers = parser.add_subparsers(dest="domain", required=True)

    project_parser = subparsers.add_parser("project")
    project_subparsers = project_parser.add_subparsers(dest="command", required=True)

    create_parser = project_subparsers.add_parser("create")
    create_parser.add_argument("name")
    create_parser.add_argument("--template", default="empty", choices=["empty", "python", "node"])

    clone_parser = project_subparsers.add_parser("clone")
    clone_parser.add_argument("name")
    clone_parser.add_argument("repo_url")
    clone_parser.add_argument("--branch", default=None)

    use_parser = project_subparsers.add_parser("use")
    use_parser.add_argument("name")

    project_subparsers.add_parser("list")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        system_config_path = validate_system_config_path(resolve_system_config(args.system_config))
        manager = ProjectManager.load(system_config_path)
        validate_manager_startup(manager, require_active_project=False)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        parser.error(str(exc))

    if args.domain == "project" and args.command == "create":
        project = manager.create_project(args.name, template=args.template)
        print(f"created {project.name} at {project.project_root}")
        return 0

    if args.domain == "project" and args.command == "clone":
        project = manager.clone_project(args.name, args.repo_url, branch=args.branch)
        print(f"cloned {project.name} at {project.project_root}")
        return 0

    if args.domain == "project" and args.command == "use":
        manager.set_active_project(args.name)
        validate_manager_startup(manager, require_active_project=True)
        print(f"active project set to {args.name}")
        return 0

    if args.domain == "project" and args.command == "list":
        active = manager.system_config.active_project
        for name in manager.list_projects():
            suffix = " *" if name == active else ""
            print(f"{name}{suffix}")
        return 0

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
