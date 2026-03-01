from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


DEFAULT_HARD_DENY = (".git", "secrets", ".env")


class PolicyViolation(ValueError):
    """Raised when a path violates the configured project policy."""


def _normalize_policy_entry(entry: str) -> PurePosixPath:
    if not entry:
        raise ValueError("Policy entry cannot be empty")
    if Path(entry).is_absolute():
        raise ValueError("Policy entries must be relative paths")
    normalized = PurePosixPath(entry.replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError("Policy entries cannot escape the project root")
    return normalized


def _matches_prefix(path: PurePosixPath, prefix: PurePosixPath) -> bool:
    return path == prefix or prefix in path.parents


@dataclass(frozen=True)
class PathPolicy:
    project_root: Path
    forbidden_subpaths: tuple[PurePosixPath, ...] = ()
    allowed_subpaths: tuple[PurePosixPath, ...] = ()
    hard_deny_subpaths: tuple[PurePosixPath, ...] = tuple(
        _normalize_policy_entry(entry) for entry in DEFAULT_HARD_DENY
    )

    @classmethod
    def from_config(
        cls,
        project_root: Path,
        forbidden_subpaths: Iterable[str] | None = None,
        allowed_subpaths: Iterable[str] | None = None,
        hard_deny_subpaths: Iterable[str] | None = None,
    ) -> "PathPolicy":
        forbidden = tuple(
            _normalize_policy_entry(entry) for entry in (forbidden_subpaths or [])
        )
        allowed = tuple(_normalize_policy_entry(entry) for entry in (allowed_subpaths or []))
        hard_deny_entries = tuple(
            _normalize_policy_entry(entry)
            for entry in (hard_deny_subpaths or DEFAULT_HARD_DENY)
        )
        return cls(
            project_root=project_root.resolve(),
            forbidden_subpaths=forbidden,
            allowed_subpaths=allowed,
            hard_deny_subpaths=hard_deny_entries,
        )

    def normalize_change_path(self, path_value: str) -> PurePosixPath:
        if not isinstance(path_value, str) or not path_value.strip():
            raise PolicyViolation("Changed file path cannot be empty")
        raw = Path(path_value)
        if raw.is_absolute():
            raise PolicyViolation(f"Absolute path is not allowed: {path_value}")
        candidate = (self.project_root / raw).resolve(strict=False)
        try:
            relative = candidate.relative_to(self.project_root)
        except ValueError as exc:
            raise PolicyViolation(f"Path escapes project root: {path_value}") from exc
        rel_posix = PurePosixPath(relative.as_posix())
        if rel_posix == PurePosixPath("."):
            raise PolicyViolation("Project root itself is not a valid changed file path")
        return rel_posix

    def normalize_change_paths(self, changed_files: Iterable[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for changed_file in changed_files:
            rel_path = self.normalize_change_path(changed_file).as_posix()
            if rel_path in seen:
                continue
            seen.add(rel_path)
            normalized.append(rel_path)
        return normalized

    def is_path_allowed(self, path_value: str) -> bool:
        try:
            rel_path = self.normalize_change_path(path_value)
        except PolicyViolation:
            return False

        for denied in self.hard_deny_subpaths:
            if _matches_prefix(rel_path, denied):
                return False

        for denied in self.forbidden_subpaths:
            if _matches_prefix(rel_path, denied):
                return False

        if not self.allowed_subpaths:
            return True

        return any(_matches_prefix(rel_path, allowed) for allowed in self.allowed_subpaths)

    def assert_changes_allowed(self, changed_files: Iterable[str]) -> None:
        normalized = self.normalize_change_paths(changed_files)
        if not normalized:
            raise PolicyViolation("No changed files were detected")
        for changed_file in normalized:
            if not self.is_path_allowed(changed_file):
                raise PolicyViolation(f"Change is not allowed: {changed_file}")
