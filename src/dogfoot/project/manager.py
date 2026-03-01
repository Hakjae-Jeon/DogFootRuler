from __future__ import annotations

import re
import shutil
import subprocess
from datetime import datetime, timezone
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

    def _ensure_project_ignore_rules(self, project_root: Path) -> None:
        ignore_path = project_root / ".gitignore"
        required_lines = ["runs/", "__pycache__/"]
        existing_lines: list[str] = []
        if ignore_path.exists():
            existing_lines = ignore_path.read_text(encoding="utf-8").splitlines()
        merged = [line for line in existing_lines if line.strip()]
        changed = False
        for line in required_lines:
            if line not in merged:
                merged.append(line)
                changed = True
        if changed or not ignore_path.exists():
            ignore_path.write_text("\n".join(merged) + "\n", encoding="utf-8")

    def _write_project_config(self, project_root: Path, name: str) -> None:
        config_dir = project_root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "project.yaml"
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

    def create_project(self, name: str, template: str = "empty") -> Project:
        if template not in {"empty", "python", "node"}:
            raise ValueError(f"Unsupported template: {template}")
        project_root = self.resolve_project_root(name)
        if project_root.exists():
            raise FileExistsError(f"Project already exists: {name}")

        (project_root / "config").mkdir(parents=True, exist_ok=True)
        (project_root / "runs").mkdir(parents=True, exist_ok=True)
        self._ensure_project_ignore_rules(project_root)
        (project_root / "README.md").write_text(f"# {name}\n", encoding="utf-8")

        if template == "python":
            src_dir = project_root / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "main.py").write_text("print('hello')\n", encoding="utf-8")
        elif template == "node":
            src_dir = project_root / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "index.js").write_text("console.log('hello');\n", encoding="utf-8")

        self._write_project_config(project_root, name)
        self._initialize_git_repo(project_root)
        return self.get_project(name)

    def clone_project(self, name: str, repo_url: str, branch: str | None = None) -> Project:
        project_root = self.resolve_project_root(name)
        if project_root.exists():
            raise FileExistsError(f"Project already exists: {name}")

        args = ["clone"]
        if branch:
            args.extend(["--branch", branch, "--single-branch"])
        args.extend([repo_url, str(project_root)])
        result = self._run_git(self.project_base_root, args)
        if result.returncode != 0:
            if project_root.exists():
                subprocess.run(["rm", "-rf", str(project_root)], check=False)
            detail = result.stderr.strip() or result.stdout.strip() or "unknown git error"
            raise RuntimeError(f"Git clone failed ({repo_url}): {detail}")

        (project_root / "runs").mkdir(parents=True, exist_ok=True)
        self._ensure_project_ignore_rules(project_root)
        self._write_project_config(project_root, name)
        return self.get_project(name)

    def get_project(self, name: str) -> Project:
        project_root = self.resolve_project_root(name)
        if not project_root.exists():
            raise FileNotFoundError(f"Project not found: {name}")
        self._ensure_project_ignore_rules(project_root)
        return Project.load(
            project_root,
            system_forbidden_subpaths=self.system_config.system_forbidden_subpaths,
            hard_deny_subpaths=self.system_config.hard_deny_subpaths,
        )

    def set_active_project(self, name: str) -> None:
        self.get_project(name)
        self.system_config.active_project = name
        self.system_config.save()

    def recover_active_project(self) -> tuple[str | None, str | None]:
        active_name = self.system_config.active_project
        if not active_name:
            return None, None
        try:
            self.get_project(active_name)
        except Exception as exc:
            self.system_config.active_project = None
            self.system_config.save()
            return active_name, str(exc)
        return None, None

    def get_active_project(self) -> Project:
        if not self.system_config.active_project:
            raise ValueError("No active project configured")
        recovered_name, recovery_reason = self.recover_active_project()
        if recovered_name:
            raise ValueError(f"active_project({recovered_name}) was cleared: {recovery_reason}")
        return self.get_project(self.system_config.active_project)

    def remove_project(self, name: str, force_delete: bool = False) -> tuple[Path, bool]:
        project_root = self.resolve_project_root(name)
        if not project_root.exists():
            raise FileNotFoundError(f"Project not found: {name}")

        removed_active = self.system_config.active_project == name
        if force_delete:
            shutil.rmtree(project_root)
            destination = project_root
        else:
            trash_root = self.project_base_root / ".trash"
            trash_root.mkdir(parents=True, exist_ok=True)
            suffix = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            destination = trash_root / f"{name}-{suffix}"
            shutil.move(str(project_root), str(destination))

        if removed_active:
            self.system_config.active_project = None
            self.system_config.save()
        return destination, removed_active

    def set_project_base_root(self, new_base_root: Path, migrate: bool = False) -> tuple[Path, list[str]]:
        resolved = new_base_root.resolve()
        if resolved.exists() and not resolved.is_dir():
            raise NotADirectoryError(f"project_base_root is not a directory: {resolved}")
        resolved.mkdir(parents=True, exist_ok=True)

        migrated_projects: list[str] = []
        current_base_root = self.project_base_root
        if migrate:
            for name in self.list_projects():
                source = self.resolve_project_root(name)
                destination = (resolved / name).resolve()
                if destination.exists():
                    raise FileExistsError(f"Destination already exists for project {name}: {destination}")
                shutil.move(str(source), str(destination))
                migrated_projects.append(name)

        self.system_config.project_base_root = resolved
        if self.system_config.active_project:
            active_root = (resolved / self.system_config.active_project).resolve()
            if not active_root.exists():
                self.system_config.active_project = None
        self.system_config.save()
        return current_base_root, migrated_projects
