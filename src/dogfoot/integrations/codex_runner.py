from __future__ import annotations

import re
import subprocess
from pathlib import Path
from threading import Lock


class CodexRunner:
    def __init__(self, timeout: int = 180, sandbox_mode: str = "workspace-write") -> None:
        self.timeout = timeout
        self.sandbox_mode = sandbox_mode
        self._processes: dict[str, subprocess.Popen] = {}
        self._lock = Lock()
        self._session_id_pattern = re.compile(r"session id:\s*([0-9a-fA-F-]{8,})", re.IGNORECASE)

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            process = self._processes.get(task_id)
            if not process:
                return False
            process.kill()
        return True

    def build_command(self, prompt: str, session_mode: str, session_id: str | None) -> list[str]:
        if session_mode == "resume" and session_id:
            return ["codex", "exec", "resume", "--full-auto", session_id, prompt]
        return ["codex", "exec", "--sandbox", self.sandbox_mode, prompt]

    def extract_session_id(self, stderr_text: str) -> str | None:
        match = self._session_id_pattern.search(stderr_text or "")
        return match.group(1) if match else None

    def run(
        self,
        task_id: str,
        prompt: str,
        project_root: Path,
        session_mode: str = "new",
        session_id: str | None = None,
    ) -> tuple[int, str, str, str, str | None]:
        process = subprocess.Popen(
            self.build_command(prompt, session_mode, session_id),
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
        discovered_session_id = self.extract_session_id(stderr or "")
        return (
            process.returncode if process.returncode is not None else 1,
            stdout or "",
            stderr or "",
            reason,
            discovered_session_id,
        )
