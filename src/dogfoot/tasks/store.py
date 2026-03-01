from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from random import SystemRandom
from typing import Any

from dogfoot.project.manager import ProjectManager
from dogfoot.project.project import Project
from dogfoot.tasks.models import Status, canonical_status


class TaskStore:
    def __init__(self, manager: ProjectManager | None, legacy_runs_dir: Path) -> None:
        self.manager = manager
        self.legacy_runs_dir = legacy_runs_dir
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.tasks: dict[str, dict[str, Any]] = {}
        self._load_existing_tasks()

    def _iter_known_task_dirs(self) -> list[Path]:
        task_dirs: list[Path] = []
        if self.legacy_runs_dir.exists():
            for entry in sorted(self.legacy_runs_dir.iterdir()):
                if entry.is_dir():
                    task_dirs.append(entry)
        if self.manager:
            for project_name in self.manager.list_projects():
                project = self.manager.get_project(project_name)
                runs_dir = project.get_runs_dir()
                for entry in sorted(runs_dir.iterdir()):
                    if entry.is_dir():
                        task_dirs.append(entry)
        return task_dirs

    def resolve_task_dir(self, task_id: str) -> Path | None:
        meta = self.tasks.get(task_id)
        if meta and meta.get("task_dir"):
            return Path(str(meta["task_dir"]))
        legacy = self.legacy_runs_dir / task_id
        if legacy.exists():
            return legacy
        for task_dir in self._iter_known_task_dirs():
            if task_dir.name == task_id:
                return task_dir
        return None

    def load_task_meta(self, task_id: str) -> dict[str, Any]:
        task_dir = self.resolve_task_dir(task_id)
        if not task_dir:
            return {}
        meta_path = task_dir / "meta.json"
        if not meta_path.exists():
            return {}
        try:
            with meta_path.open("r", encoding="utf-8") as fh:
                meta = json.load(fh)
            status = canonical_status(meta.get("status"))
            if status:
                meta["status"] = status
            else:
                meta.setdefault("status", Status.READY_TO_APPLY)
            return meta
        except json.JSONDecodeError:
            return {}

    def _load_existing_tasks(self) -> None:
        for entry in self._iter_known_task_dirs():
            meta = self.load_task_meta(entry.name)
            if not meta:
                continue
            task_id = meta.get("task_id") or entry.name
            meta.setdefault("task_dir", str(entry))
            self.tasks[task_id] = meta
            if meta.get("status") == Status.QUEUED:
                self.queue.put_nowait(task_id)

    def _meta_path(self, task_id: str) -> Path:
        task_dir = self.resolve_task_dir(task_id)
        if not task_dir:
            raise FileNotFoundError(f"Task directory not found: {task_id}")
        return task_dir / "meta.json"

    def task_dir(self, task_id: str) -> Path | None:
        task_dir = self.resolve_task_dir(task_id)
        if task_dir and task_id in self.tasks:
            self.tasks[task_id]["task_dir"] = str(task_dir)
        return task_dir

    def _persist_meta(self, task_id: str) -> None:
        meta_path = self._meta_path(task_id)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with meta_path.open("w", encoding="utf-8") as fh:
            json.dump(self.tasks[task_id], fh, ensure_ascii=False, indent=2)

    def _new_task_id(self) -> str:
        now = datetime.now(timezone.utc)
        suffix = "".join(SystemRandom().choice("0123456789abcdef") for _ in range(6))
        return f"{now:%Y%m%d-%H%M%S}-{suffix}"

    def create_task(self, user_id: int, chat_id: int, text: str, project: Project) -> str:
        task_id = self._new_task_id()
        task_dir = project.get_runs_dir() / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "request.txt").write_text(text, encoding="utf-8")
        meta = {
            "task_id": task_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": Status.QUEUED,
            "user_id": user_id,
            "chat_id": chat_id,
            "request": text,
            "project_name": project.name,
            "project_root": str(project.project_root),
            "task_dir": str(task_dir),
        }
        self.tasks[task_id] = meta
        self._persist_meta(task_id)
        self.queue.put_nowait(task_id)
        return task_id

    def update_meta(self, task_id: str, **updates: Any) -> None:
        meta = self.tasks.get(task_id)
        if not meta:
            return
        meta.update(updates)
        self._persist_meta(task_id)

    def status_summary(self) -> str:
        queued = [tid for tid, meta in self.tasks.items() if meta.get("status") == Status.QUEUED]
        running = [tid for tid, meta in self.tasks.items() if meta.get("status") == Status.RUNNING]
        finished_states = {
            Status.READY_TO_APPLY,
            Status.APPLIED,
            Status.COMMITTED,
            Status.MERGED,
            Status.FAILED,
            Status.CANCELED,
        }
        done = [tid for tid, meta in self.tasks.items() if meta.get("status") in finished_states]
        ready = [tid for tid, meta in self.tasks.items() if meta.get("status") == Status.READY_TO_APPLY]
        applied = [tid for tid, meta in self.tasks.items() if meta.get("status") == Status.APPLIED]
        committed = [tid for tid, meta in self.tasks.items() if meta.get("status") == Status.COMMITTED]
        merged = [tid for tid, meta in self.tasks.items() if meta.get("status") == Status.MERGED]
        canceled = [tid for tid, meta in self.tasks.items() if meta.get("status") == Status.CANCELED]
        lines = [f"RUNNING: {len(running)}", f"QUEUED: {len(queued)}"]
        if queued:
            lines.append("큐 상위: " + ", ".join(queued[:3]))
        if ready:
            lines.append("READY_TO_APPLY: " + ", ".join(ready[:3]))
        if applied:
            lines.append("APPLIED: " + ", ".join(applied[:3]))
        if committed:
            lines.append("COMMITTED: " + ", ".join(committed[:3]))
        lines.append(f"최근 완료: {len(done)}")
        if merged:
            lines.append("MERGED: " + ", ".join(merged[:3]))
        if canceled:
            lines.append("CANCELED: " + ", ".join(canceled[:3]))
        return "\n".join(lines)
