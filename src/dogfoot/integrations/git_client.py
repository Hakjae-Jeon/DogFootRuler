from __future__ import annotations

import subprocess
from pathlib import Path


class GitClient:
    def __init__(self, main_branch: str = "main") -> None:
        self.main_branch = main_branch

    def run(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)

    def ensure_task_branch(self, task_id: str, project_root: Path) -> str:
        branch = f"dfr/task/{task_id}"
        result = self.run(["rev-parse", "--verify", branch], cwd=project_root)
        if result.returncode != 0:
            self.run(["branch", branch, self.main_branch], cwd=project_root)
        return branch

    def generate_diff(self, branch: str, project_root: Path) -> str:
        return self.run(["diff", f"{self.main_branch}..{branch}"], cwd=project_root).stdout or ""

    def changed_files(self, branch: str, project_root: Path) -> list[str]:
        result = self.run(["diff", "--name-only", f"{self.main_branch}..{branch}"], cwd=project_root)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def checkout_branch(self, branch: str, project_root: Path) -> tuple[bool, str]:
        result = self.run(["checkout", branch], cwd=project_root)
        if result.returncode != 0:
            return False, result.stderr.strip() or result.stdout.strip()
        return True, ""

    def apply_diff_file(self, diff_path: Path, project_root: Path) -> subprocess.CompletedProcess:
        return self.run(["apply", "--whitespace=fix", str(diff_path)], cwd=project_root)

    def workspace_is_clean(self, project_root: Path) -> bool:
        return not self.run(["status", "--porcelain"], cwd=project_root).stdout.strip()

    def stage_all(self, project_root: Path) -> None:
        self.run(["add", "-A"], cwd=project_root)

    def commit(self, message: str, project_root: Path) -> subprocess.CompletedProcess:
        return self.run(["commit", "-m", message], cwd=project_root)

    def head(self, project_root: Path) -> str:
        return self.run(["rev-parse", "HEAD"], cwd=project_root).stdout.strip()

    def merge_no_ff(self, branch: str, project_root: Path) -> subprocess.CompletedProcess:
        return self.run(["merge", "--no-ff", branch], cwd=project_root)

    def merge_abort(self, project_root: Path) -> None:
        self.run(["merge", "--abort"], cwd=project_root)

    def tidy_workspace(self, project_root: Path) -> None:
        self.run(["reset", "--hard"], cwd=project_root)
        self.run(["clean", "-fd"], cwd=project_root)
        self.checkout_branch(self.main_branch, project_root)
