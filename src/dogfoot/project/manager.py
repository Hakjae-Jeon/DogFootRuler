from __future__ import annotations

import re
import subprocess
from pathlib import Path

from dogfoot.config.system import SystemConfig
from dogfoot.project.project import Project
from dogfoot.utils.simple_yaml import dump_simple_yaml

PROJECT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class ProjectManager:
    def __init__(self, system_config: SystemConfig) -> None:
        self.system_config = system_config
        base_root = self.system_config.project_base_root
        if base_root.exists() and not base_root.is_dir():
            raise NotADirectoryError(f"project_base_root is not a directory: {base_root}")
        base_root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls, system_config_path: Path) -> "ProjectManager":
        return cls(SystemConfig.load(system_config_path))

    @property
    def project_base_root(self) -> Path:
        return self.system_config.project_base_root

    def _validate_project_name(self, name: str) -> None:
        if not PROJECT_NAME_PATTERN.fullmatch(name):
            raise ValueError(f"Invalid project name: {name}")

    def resolve_project_root(self, name: str) -> Path:
        self._validate_project_name(name)
        return (self.project_base_root / name).resolve()

    def list_projects(self) -> list[str]:
        projects: list[str] = []
        for entry in sorted(self.project_base_root.iterdir()):
            if not entry.is_dir():
                continue
            if (entry / "config" / "project.yaml").exists():
                projects.append(entry.name)
        return projects

    def _run_git(self, project_root: Path, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git"] + args,
            cwd=project_root,
            capture_output=True,
            text=True,
        )

    def _initialize_git_repo(self, project_root: Path) -> None:
        commands = [
            ["init", "-b", "main"],
            ["config", "user.name", "DogFootRuler"],
            ["config", "user.email", "dogfootruler@local"],
            ["add", "-A"],
            ["commit", "-m", "Initial commit"],
        ]
        for args in commands:
            result = self._run_git(project_root, args)
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip() or "unknown git error"
                raise RuntimeError(f"Git initialization failed ({' '.join(args)}): {detail}")

    def create_project(self, name: str, template: str = "empty") -> Project:
        if template not in {"empty", "python", "node"}:
            raise ValueError(f"Unsupported template: {template}")
        project_root = self.resolve_project_root(name)
        if project_root.exists():
            raise FileExistsError(f"Project already exists: {name}")

        (project_root / "config").mkdir(parents=True, exist_ok=True)
        (project_root / "runs").mkdir(parents=True, exist_ok=True)
        (project_root / ".gitignore").write_text("runs/\n__pycache__/\n", encoding="utf-8")
        (project_root / "README.md").write_text(f"# {name}\n", encoding="utf-8")

        if template == "python":
            src_dir = project_root / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "main.py").write_text("print('hello')\n", encoding="utf-8")
        elif template == "node":
            src_dir = project_root / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "index.js").write_text("console.log('hello');\n", encoding="utf-8")

        config_path = project_root / "config" / "project.yaml"
        config_path.write_text(
            dump_simple_yaml(
                {
                    "name": name,
                    "forbidden_subpaths": [],
                    "allowed_subpaths": [],
                }
            ),
            encoding="utf-8",
        )
        self._initialize_git_repo(project_root)
        return self.get_project(name)

    def get_project(self, name: str) -> Project:
        project_root = self.resolve_project_root(name)
        if not project_root.exists():
            raise FileNotFoundError(f"Project not found: {name}")
        return Project.load(
            project_root,
            system_forbidden_subpaths=self.system_config.system_forbidden_subpaths,
            hard_deny_subpaths=self.system_config.hard_deny_subpaths,
        )

    def set_active_project(self, name: str) -> None:
        self.get_project(name)
        self.system_config.active_project = name
        self.system_config.save()

    def get_active_project(self) -> Project:
        if not self.system_config.active_project:
            raise ValueError("No active project configured")
        return self.get_project(self.system_config.active_project)
