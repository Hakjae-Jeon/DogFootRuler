from __future__ import annotations

import subprocess
from pathlib import Path
from threading import Lock


class CodexRunner:
    def __init__(self, timeout: int = 180, sandbox_mode: str = "workspace-write") -> None:
        self.timeout = timeout
        self.sandbox_mode = sandbox_mode
        self._processes: dict[str, subprocess.Popen] = {}
        self._lock = Lock()

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            process = self._processes.get(task_id)
            if not process:
                return False
            process.kill()
        return True

    def run(self, task_id: str, prompt: str, project_root: Path) -> tuple[int, str, str, str]:
        process = subprocess.Popen(
            ["codex", "exec", "--sandbox", self.sandbox_mode, prompt],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=project_root,
        )
        with self._lock:
            self._processes[task_id] = process
        reason = ""
        try:
            stdout, stderr = process.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            reason = "timeout"
        except Exception as exc:
            stdout, stderr = "", str(exc)
            reason = "error"
        finally:
            with self._lock:
                self._processes.pop(task_id, None)
        return process.returncode if process.returncode is not None else 1, stdout or "", stderr or "", reason
