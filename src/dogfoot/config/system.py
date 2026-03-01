from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dogfoot.project.policy import DEFAULT_HARD_DENY
from dogfoot.utils.simple_yaml import dump_simple_yaml, load_simple_yaml


@dataclass
class SystemConfig:
    system_config_path: Path
    project_base_root: Path
    active_project: str | None = None
    system_forbidden_subpaths: list[str] | None = None
    hard_deny_subpaths: list[str] | None = None

    @classmethod
    def load(cls, system_config_path: Path) -> "SystemConfig":
        path = system_config_path.resolve()
        raw = load_simple_yaml(path)
        base_root_value = raw.get("project_base_root")
        if not base_root_value:
            raise ValueError("system.yaml must define project_base_root")
        return cls(
            system_config_path=path,
            project_base_root=Path(str(base_root_value)).resolve(),
            active_project=(raw.get("active_project") or None),
            system_forbidden_subpaths=list(raw.get("system_forbidden_subpaths") or []),
            hard_deny_subpaths=list(raw.get("hard_deny_subpaths") or DEFAULT_HARD_DENY),
        )

    def save(self) -> None:
        self.system_config_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "project_base_root": str(self.project_base_root),
            "active_project": self.active_project or "",
            "system_forbidden_subpaths": self.system_forbidden_subpaths or [],
            "hard_deny_subpaths": self.hard_deny_subpaths or list(DEFAULT_HARD_DENY),
        }
        self.system_config_path.write_text(dump_simple_yaml(payload), encoding="utf-8")
