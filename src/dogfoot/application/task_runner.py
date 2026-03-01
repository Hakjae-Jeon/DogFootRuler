from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from dogfoot.application.artifacts import (
    build_failure_summary_text,
    build_stdout_text,
    build_summary_text,
    mask_sensitive,
)
from dogfoot.integrations.codex_runner import CodexRunner
from dogfoot.integrations.git_client import GitClient
from dogfoot.project.policy import PolicyViolation
from dogfoot.project.project import Project
from dogfoot.tasks.models import Status
from dogfoot.tasks.store import TaskStore


class TaskRunner:
    def __init__(
        self,
        task_store: TaskStore,
        git_client: GitClient,
        codex_runner: CodexRunner,
        project_loader: Callable[[dict], Project],
        notifier: Callable[[str, str], Awaitable[None]],
        logger: logging.Logger,
    ) -> None:
        self.task_store = task_store
        self.git_client = git_client
        self.codex_runner = codex_runner
        self.project_loader = project_loader
        self.notifier = notifier
        self.logger = logger

    async def process_task(self, task_id: str) -> None:
        meta = self.task_store.load_task_meta(task_id)
        if not meta:
            raise FileNotFoundError(f"Task meta not found: {task_id}")
        task_dir = self.task_store.resolve_task_dir(task_id)
        if not task_dir:
            raise FileNotFoundError(f"Task directory not found: {task_id}")
        project = self.project_loader(meta)
        request_text = (task_dir / "request.txt").read_text(encoding="utf-8").strip()
        started = datetime.now(timezone.utc).isoformat()
        branch = self.git_client.ensure_task_branch(task_id, project.project_root)
        try:
            if not self.git_client.workspace_is_clean(project.project_root):
                note = "Codex 실행을 위한 작업 트리가 깨끗하지 않습니다."
                self.task_store.update_meta(
                    task_id,
                    status=Status.FAILED,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    notes=note,
                )
                await self.notifier(task_id, f"Task {task_id} 실패: {note}")
                return

            ok, checkout_err = self.git_client.checkout_branch(branch, project.project_root)
            if not ok:
                note = f"브랜치 체크아웃 실패: {checkout_err}"
                self.task_store.update_meta(
                    task_id,
                    status=Status.FAILED,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    notes=note,
                )
                await self.notifier(task_id, f"Task {task_id} 실패: {note}")
                return

            self.task_store.update_meta(task_id, branch=branch, status=Status.RUNNING, started_at=started)

            return_code, stdout_capture, stderr_capture, reason = self.codex_runner.run(
                task_id, request_text, project.project_root
            )
            stdout_text = mask_sensitive(stdout_capture or build_stdout_text(task_id, request_text))
            stderr_text = mask_sensitive(stderr_capture or "")
            (task_dir / "stdout.log").write_text(stdout_text, encoding="utf-8")
            (task_dir / "stderr.log").write_text(stderr_text, encoding="utf-8")
            stdout_sample = stdout_text.strip().splitlines()[:3]
            stdout_excerpt = " | ".join(stdout_sample) if stdout_sample else "없음"
            stderr_sample = stderr_text.strip().splitlines()[:3]
            stderr_excerpt = " | ".join(stderr_sample) if stderr_sample else "없음"
            current_meta = self.task_store.load_task_meta(task_id)
            if current_meta.get("status") == Status.CANCELED:
                canceled_summary = mask_sensitive(
                    f"Task {task_id}이(가) 사용자 취소로 종료되었습니다 (reason={reason or 'cancelled'})."
                )
                (task_dir / "summary.md").write_text(canceled_summary, encoding="utf-8")
                self.task_store.update_meta(
                    task_id,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    notes="사용자 취소",
                )
                await self.notifier(task_id, canceled_summary)
                return

            diff_text = self.git_client.generate_diff(branch, project.project_root)
            changed_files = self.git_client.changed_files(branch, project.project_root)
            diff_path = task_dir / "diff.patch"
            diff_exists = bool(diff_text.strip())
            if diff_exists:
                diff_path.write_text(diff_text, encoding="utf-8")
            elif diff_path.exists():
                diff_path.unlink()
            execution_note = reason or "정상"
            try:
                changed_files = project.policy.normalize_change_paths(changed_files)
                project.assert_changes_allowed(changed_files)
            except PolicyViolation as exc:
                failure_summary = mask_sensitive(
                    build_failure_summary_text(
                        task_id=task_id,
                        project_name=project.name,
                        request=request_text,
                        failure_reason=str(exc),
                        stdout_sample=stdout_excerpt,
                        stderr_sample=stderr_excerpt,
                        execution_note=execution_note,
                    )
                )
                (task_dir / "summary.md").write_text(failure_summary, encoding="utf-8")
                self.task_store.update_meta(
                    task_id,
                    status=Status.FAILED,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    changed_files=changed_files,
                    notes=str(exc),
                    stdout_excerpt=stdout_excerpt,
                    stderr_excerpt=stderr_excerpt,
                    execution_note=execution_note,
                )
                await self.notifier(task_id, failure_summary)
                return

            summary_text = build_summary_text(
                task_id,
                project.name,
                request_text,
                return_code,
                stderr_excerpt,
                diff_exists,
                execution_note,
            )
            masked_summary = mask_sensitive(summary_text)
            (task_dir / "summary.md").write_text(masked_summary, encoding="utf-8")
            self.task_store.update_meta(
                task_id,
                status=Status.READY_TO_APPLY,
                ready_at=datetime.now(timezone.utc).isoformat(),
                return_code=return_code,
                stderr_excerpt=stderr_excerpt,
                diff_exists=diff_exists,
                changed_files=changed_files,
                diff_path=str(diff_path) if diff_exists else None,
                notes="PR3 Codex 실행 완료",
                execution_note=execution_note,
            )
            await self.notifier(task_id, masked_summary)
        finally:
            self.git_client.tidy_workspace(project.project_root)

    async def queue_worker(self) -> None:
        try:
            while True:
                try:
                    task_id = await self.task_store.queue.get()
                except asyncio.CancelledError:
                    self.logger.info("큐 워커가 취소되어 종료 중")
                    break
                meta = self.task_store.load_task_meta(task_id)
                if meta.get("status") == Status.CANCELED:
                    self.task_store.queue.task_done()
                    continue
                try:
                    self.logger.info("큐 워커가 작업 %s 실행", task_id)
                    await self.process_task(task_id)
                except Exception:
                    self.logger.exception("작업 %s 처리 중 오류", task_id)
                    self.task_store.update_meta(task_id, status=Status.FAILED, notes="큐 처리 중 예외")
                finally:
                    self.task_store.queue.task_done()
        except asyncio.CancelledError:
            self.logger.info("큐 워커 루프가 취소됨")
