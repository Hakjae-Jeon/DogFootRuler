from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dogfoot.project.policy import PathPolicy
from dogfoot.utils.simple_yaml import dump_simple_yaml, load_simple_yaml


@dataclass
class Project:
    name: str
    project_root: Path
    config_path: Path
    config: dict[str, Any] = field(default_factory=dict)
    policy: PathPolicy | None = None

    def __post_init__(self) -> None:
        self.project_root = self.project_root.resolve()
        self.config_path = self.config_path.resolve()
        if self.policy is None:
            self.policy = self._build_policy(self.config)

    @classmethod
    def load(
        cls,
        project_root: Path,
        system_forbidden_subpaths: list[str] | None = None,
        hard_deny_subpaths: list[str] | None = None,
    ) -> "Project":
        root = project_root.resolve()
        config_path = root / "config" / "project.yaml"
        config = load_simple_yaml(config_path)
        name = str(config.get("name") or root.name)
        project = cls(
            name=name,
            project_root=root,
            config_path=config_path,
            config=config,
        )
        project.policy = project._build_policy(
            config,
            system_forbidden_subpaths=system_forbidden_subpaths,
            hard_deny_subpaths=hard_deny_subpaths,
        )
        return project

    def _build_policy(
        self,
        config: dict[str, Any],
        system_forbidden_subpaths: list[str] | None = None,
        hard_deny_subpaths: list[str] | None = None,
    ) -> PathPolicy:
        combined_forbidden = list(system_forbidden_subpaths or [])
        combined_forbidden.extend(config.get("forbidden_subpaths") or [])
        return PathPolicy.from_config(
            project_root=self.project_root,
            forbidden_subpaths=combined_forbidden,
            allowed_subpaths=config.get("allowed_subpaths") or [],
            hard_deny_subpaths=hard_deny_subpaths,
        )

    def validate_startup(self) -> None:
        if not self.project_root.exists():
            raise FileNotFoundError(f"Project root does not exist: {self.project_root}")
        if not self.config_path.exists():
            raise FileNotFoundError(f"Project config does not exist: {self.config_path}")
        if self.get_runs_dir().exists() and not self.get_runs_dir().is_dir():
            raise NotADirectoryError(f"Runs path is not a directory: {self.get_runs_dir()}")

    def get_runs_dir(self) -> Path:
        runs_dir = self.project_root / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        return runs_dir

    def is_path_allowed(self, rel_path: str) -> bool:
        return self.policy.is_path_allowed(rel_path)

    def assert_changes_allowed(self, changed_files: list[str]) -> None:
        self.policy.assert_changes_allowed(changed_files)

    def save_config(self) -> None:
        serializable = {
            "name": self.name,
            "forbidden_subpaths": self.config.get("forbidden_subpaths") or [],
            "allowed_subpaths": self.config.get("allowed_subpaths") or [],
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(dump_simple_yaml(serializable), encoding="utf-8")
