from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from random import SystemRandom
from threading import Lock
from typing import Any, Dict, Tuple
from zipfile import ZipFile

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_BRANCH = "main"

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
RUNS_DIR = Path("runs")
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
CODEX_TIMEOUT = 180
LOG_ARCHIVE_NAME = "artifacts.zip"
TOKEN_PATTERN = re.compile(r"(?i)((token|key|secret)\s*[:=]\s*)([\w-]+)")
codex_processes: Dict[str, subprocess.Popen] = {}
codex_lock = Lock()
logger = logging.getLogger(__name__)


def run_git_command(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def load_task_meta(task_id: str) -> Dict[str, Any]:
    meta_path = RUNS_DIR / task_id / "meta.json"
    if not meta_path.exists():
        return {}
    try:
        with meta_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        return {}


def ensure_task_branch(task_id: str) -> str:
    branch = f"dfr/task/{task_id}"
    result = run_git_command(["rev-parse", "--verify", branch])
    if result.returncode != 0:
        run_git_command(["branch", branch, MAIN_BRANCH])
    return branch


def generate_git_diff(branch: str) -> str:
    diff_result = run_git_command(["diff", f"{MAIN_BRANCH}..{branch}"])
    return diff_result.stdout or ""


def mask_sensitive(text: str) -> str:
    return TOKEN_PATTERN.sub(lambda m: f"{m.group(1)}***", text)


def create_artifacts_zip(task_id: str) -> Path:
    zip_path = RUNS_DIR / task_id / LOG_ARCHIVE_NAME
    files_to_zip = ["request.txt", "stdout.log", "stderr.log", "summary.md", "diff.patch"]
    with ZipFile(zip_path, "w") as archive:
        for name in files_to_zip:
            source = RUNS_DIR / task_id / name
            if source.exists():
                archive.write(source, arcname=name)
    return zip_path


def cancel_running_task(task_id: str) -> bool:
    with codex_lock:
        process = codex_processes.get(task_id)
        if not process:
            return False
        process.kill()
    return True


def checkout_branch(branch: str) -> Tuple[bool, str]:
    result = run_git_command(["checkout", branch])
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    return True, ""


def apply_diff_file(diff_path: Path) -> subprocess.CompletedProcess:
    return run_git_command(["apply", "--whitespace=fix", str(diff_path)])


def workspace_is_clean() -> bool:
    status = run_git_command(["status", "--porcelain"])
    return not status.stdout.strip()


def parse_scalar(raw: str) -> Any:
    trimmed = raw.strip()
    if not trimmed:
        return ""
    if trimmed[0] in "'\"" and trimmed.endswith(trimmed[0]) and len(trimmed) >= 2:
        return trimmed[1:-1]
    lowered = trimmed.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if trimmed.startswith("[") and trimmed.endswith("]"):
        inner = trimmed[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",")]
    if re.fullmatch(r"-?\d+", trimmed):
        return int(trimmed)
    return trimmed


def load_simple_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    data: Dict[str, Any] = {}
    current_list_key: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.split("#", 1)[0].strip()
        if not cleaned:
            continue
        if cleaned.startswith("- "):
            if current_list_key:
                data.setdefault(current_list_key, []).append(parse_scalar(cleaned[2:].strip()))
            continue
        if ":" not in cleaned:
            current_list_key = None
            continue
        key, value = map(str.strip, cleaned.split(":", 1))
        if not value:
            data[key] = []
            current_list_key = key
            continue
        parsed = parse_scalar(value)
        data[key] = parsed
        current_list_key = key if isinstance(parsed, list) else None
    return data


class TaskStore:
    def __init__(self, runs_root: Path) -> None:
        self.runs_root = runs_root
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self._load_existing_tasks()

    def _load_existing_tasks(self) -> None:
        for entry in sorted(self.runs_root.iterdir()):
            if not entry.is_dir():
                continue
            meta_path = entry / "meta.json"
            if not meta_path.exists():
                continue
            try:
                with meta_path.open("r", encoding="utf-8") as fh:
                    meta = json.load(fh)
            except json.JSONDecodeError:
                logger.warning("이전 메타(%s)가 파싱 실패해서 건너뜁니다.", entry.name)
                continue
            task_id = meta.get("task_id") or entry.name
            self.tasks[task_id] = meta
            if meta.get("status") == "QUEUED":
                self.queue.put_nowait(task_id)

    def _meta_path(self, task_id: str) -> Path:
        return self.runs_root / task_id / "meta.json"

    def _persist_meta(self, task_id: str) -> None:
        meta_path = self._meta_path(task_id)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with meta_path.open("w", encoding="utf-8") as fh:
            json.dump(self.tasks[task_id], fh, ensure_ascii=False, indent=2)

    def _new_task_id(self) -> str:
        now = datetime.now(timezone.utc)
        suffix = "".join(SystemRandom().choice("0123456789abcdef") for _ in range(6))
        return f"{now:%Y%m%d-%H%M%S}-{suffix}"

    def create_task(self, user_id: int, text: str) -> str:
        task_id = self._new_task_id()
        task_dir = self.runs_root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "request.txt").write_text(text, encoding="utf-8")
        meta = {
            "task_id": task_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "QUEUED",
            "user_id": user_id,
            "request": text,
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

    def count_status(self, status: str) -> int:
        return sum(1 for meta in self.tasks.values() if meta.get("status") == status)

    def status_summary(self) -> str:
        queued = [tid for tid, meta in self.tasks.items() if meta.get("status") == "QUEUED"]
        running = [tid for tid, meta in self.tasks.items() if meta.get("status") == "RUNNING"]
        finished_states = {"READY_TO_APPLY", "APPLIED", "COMMITTED", "MERGED", "FAILED", "CANCELED"}
        done = [
            tid
            for tid, meta in self.tasks.items()
            if meta.get("status") in finished_states
        ]
        ready = [tid for tid, meta in self.tasks.items() if meta.get("status") == "READY_TO_APPLY"]
        applied = [tid for tid, meta in self.tasks.items() if meta.get("status") == "APPLIED"]
        committed = [tid for tid, meta in self.tasks.items() if meta.get("status") == "COMMITTED"]
        merged = [tid for tid, meta in self.tasks.items() if meta.get("status") == "MERGED"]
        canceled = [tid for tid, meta in self.tasks.items() if meta.get("status") == "CANCELED"]
        lines = [
            f"RUNNING: {len(running)}",
            f"QUEUED: {len(queued)}",
        ]
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


task_store = TaskStore(RUNS_DIR)


def load_configuration() -> Dict[str, Any]:
    token_path = CONFIG_DIR / "telegram.yaml"
    token_conf = load_simple_yaml(token_path)
    allowed_conf = load_simple_yaml(CONFIG_DIR / "allowed_users.yaml")
    allowed = allowed_conf.get("allowed_user_ids") or []
    allowed_ids = [int(v) for v in allowed if isinstance(v, (int, str))]
    return {
        "token": token_conf.get("token"),
        "allowed_user_ids": allowed_ids,
    }


async def _not_allowed(update: Update) -> None:
    if not update.message:
        return
    await update.message.reply_text("권한이 없습니다. allowlist에 Telegram user_id를 추가하세요.")


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text("pong")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    commands = ["/ping", "/status", "/help", "자연어 작업 요청"]
    if update.message:
        await update.message.reply_text("사용 가능한 명령:\n" + "\n".join(commands))


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    summary = task_store.status_summary()
    if update.message:
        await update.message.reply_text(summary)


async def diff_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("/diff <task_id> 형식으로 요청해주세요.")
        return
    task_id = context.args[0]
    diff_path = RUNS_DIR / task_id / "diff.patch"
    branch = load_task_meta(task_id).get("branch") or f"dfr/task/{task_id}"
    if not diff_path.exists() or diff_path.stat().st_size == 0:
        await update.message.reply_text(f"{task_id}에 대한 diff가 생성되지 않았거나 변경 없음.")
        return
    if update.message:
        await update.message.reply_text(f"{task_id} ({branch}) diff.patch 첨부합니다.")
        with diff_path.open("rb") as fh:
            await update.message.reply_document(document=fh, filename=f"{task_id}-diff.patch")


async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("/logs <task_id>로 artifact zip을 받아보세요.")
        return
    task_id = context.args[0]
    zip_path = create_artifacts_zip(task_id)
    if not zip_path.exists() or zip_path.stat().st_size == 0:
        await update.message.reply_text(f"{task_id}에 로그가 생성되지 않았습니다.")
        return
    if update.message:
        await update.message.reply_text(f"{task_id} 로그 아카이브를 전송합니다.")
        with zip_path.open("rb") as fh:
            await update.message.reply_document(document=fh, filename=f"{task_id}-artifacts.zip")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("/cancel <task_id>로 큐/실행을 취소하세요.")
        return
    task_id = context.args[0]
    meta = load_task_meta(task_id)
    if not meta:
        await update.message.reply_text(f"{task_id} 메타가 없습니다.")
        return
    status = meta.get("status")
    if status == "QUEUED":
        task_store.update_meta(
            task_id,
            status="CANCELED",
            notes="사용자 취소(큐)",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        await update.message.reply_text(f"{task_id}을(를) 큐에서 취소했습니다.")
        return
    if status == "RUNNING":
        if cancel_running_task(task_id):
            task_store.update_meta(
                task_id,
                status="CANCELED",
                notes="사용자 취소(실행 중)",
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            await update.message.reply_text(f"{task_id} 실행을 취소했습니다.")
        else:
            await update.message.reply_text(f"{task_id}을(를) 취소할 수 없습니다.")
        return
    await update.message.reply_text(f"{task_id}은(는) 현재 {status} 상태여서 취소할 수 없습니다.")


async def apply_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("/apply <task_id>로 diff를 적용하세요.")
        return
    task_id = context.args[0]
    meta = load_task_meta(task_id)
    if not meta:
        await update.message.reply_text(f"{task_id} 메타가 없습니다.")
        return
    status = meta.get("status")
    if status != "READY_TO_APPLY":
        await update.message.reply_text(f"{task_id} 상태가 {status}라 적용할 수 없습니다.")
        return
    diff_path = RUNS_DIR / task_id / "diff.patch"
    if not diff_path.exists():
        await update.message.reply_text(f"{task_id}에 diff가 없습니다.")
        return
    if not workspace_is_clean():
        await update.message.reply_text("작업 트리가 깨끗해야 합니다. `git status`를 확인하세요.")
        return
    branch = meta.get("branch") or ensure_task_branch(task_id)
    ok, err = checkout_branch(branch)
    if not ok:
        await update.message.reply_text(f"브랜치 체크아웃 실패: {err}")
        return
    apply_result = apply_diff_file(diff_path)
    if apply_result.returncode != 0:
        await update.message.reply_text(f"diff 적용 실패: {apply_result.stderr.strip()}")
        return
    run_git_command(["add", "-A"])
    task_store.update_meta(
        task_id,
        status="APPLIED",
        applied_at=datetime.now(timezone.utc).isoformat(),
        notes="diff 수동 적용 완료",
    )
    await update.message.reply_text(f"{task_id} diff가 {branch}에 적용되었습니다.")


async def commit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("/commit <task_id> <message> 형식으로 입력하세요.")
        return
    task_id = context.args[0]
    message = " ".join(context.args[1:]).strip()
    if not message:
        await update.message.reply_text("커밋 메시지를 입력하세요.")
        return
    meta = load_task_meta(task_id)
    if not meta:
        await update.message.reply_text(f"{task_id} 메타가 없습니다.")
        return
    status = meta.get("status")
    if status == "COMMITTED":
        await update.message.reply_text(f"{task_id}은 이미 커밋되었습니다.")
        return
    if status != "APPLIED":
        await update.message.reply_text(f"{task_id}이 아직 적용 상태가 아닙니다 (현재 {status}).")
        return
    branch = meta.get("branch") or ensure_task_branch(task_id)
    ok, err = checkout_branch(branch)
    if not ok:
        await update.message.reply_text(f"브랜치 체크아웃 실패: {err}")
        return
    commit_result = run_git_command(["commit", "-m", message])
    if commit_result.returncode != 0:
        await update.message.reply_text(f"커밋 실패: {commit_result.stderr.strip()}")
        return
    commit_hash = run_git_command(["rev-parse", "HEAD"]).stdout.strip()
    task_store.update_meta(
        task_id,
        status="COMMITTED",
        commit_hash=commit_hash,
        commit_message=message,
        committed_at=datetime.now(timezone.utc).isoformat(),
        notes="PR5 커밋 완료",
    )
    await update.message.reply_text(f"{task_id} 커밋 완료: {commit_hash}")


async def merge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("/merge <task_id>로 main에 병합하세요.")
        return
    task_id = context.args[0]
    meta = load_task_meta(task_id)
    if not meta:
        await update.message.reply_text(f"{task_id} 메타가 없습니다.")
        return
    status = meta.get("status")
    if status == "MERGED":
        await update.message.reply_text(f"{task_id}은 이미 main에 병합되었습니다.")
        return
    if status != "COMMITTED":
        await update.message.reply_text(f"{task_id}은 커밋되지 않았습니다 (현재 {status}).")
        return
    branch = meta.get("branch") or ensure_task_branch(task_id)
    if not workspace_is_clean():
        await update.message.reply_text("main 브랜치를 병합하려면 작업 트리가 깨끗해야 합니다.")
        return
    ok, err = checkout_branch(MAIN_BRANCH)
    if not ok:
        await update.message.reply_text(f"{MAIN_BRANCH} 체크아웃 실패: {err}")
        return
    merge_result = run_git_command(["merge", "--no-ff", branch])
    if merge_result.returncode != 0:
        run_git_command(["merge", "--abort"])
        await update.message.reply_text(
            f"병합 실패: {merge_result.stderr.strip() or merge_result.stdout.strip()}"
        )
        return
    merge_commit = run_git_command(["rev-parse", "HEAD"]).stdout.strip()
    task_store.update_meta(
        task_id,
        status="MERGED",
        merge_commit=merge_commit,
        merged_at=datetime.now(timezone.utc).isoformat(),
        notes="PR5 머지 완료",
    )
    await update.message.reply_text(f"{task_id}이 main에 병합되었습니다 ({merge_commit}).")


async def natural_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("작업 지시를 입력해주세요.")
        return
    task_id = task_store.create_task(user_id, text)
    queue_size = task_store.queue.qsize()
    await update.message.reply_text(
        f"작업 {task_id}이(가) 예약되었습니다. 현재 대기 중: {queue_size}개. /status, /diff, /apply를 확인하세요."
    )


def _build_stdout_text(task_id: str, request: str) -> str:
    return (
        f"Task {task_id} 실행 시작\n"
        f"요청: {request[:200]}\n"
        f"시간: {datetime.now(timezone.utc).isoformat()}\n"
    )


def _build_summary_text(
    task_id: str,
    request: str,
    return_code: int,
    stderr_sample: str,
    diff_exists: bool,
    execution_note: str,
) -> str:
    status_text = "성공" if return_code == 0 else "실패"
    return (
        f"Task {task_id} 처리 결과: {status_text}\n"
        f"원본 요청: {request}\n"
        f"다음 단계: /diff {task_id}, /logs {task_id}\n"
        f"Codex 명령: codex exec \"{request}\"\n"
        f"stderr 요약: {stderr_sample}\n"
        f"Diff 생성 여부: {'있음' if diff_exists else '없음'}\n"
        f"실행 노트: {execution_note}\n"
    )


def _run_codex(task_id: str, prompt: str) -> Tuple[int, str, str, str]:
    process = subprocess.Popen(
        ["codex", "exec", prompt],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=REPO_ROOT,
    )
    with codex_lock:
        codex_processes[task_id] = process
    reason = ""
    try:
        stdout, stderr = process.communicate(timeout=CODEX_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        reason = "timeout"
    except Exception as exc:
        logger.exception("Codex 실행 오류")
        stdout, stderr = "", str(exc)
        reason = "error"
    finally:
        with codex_lock:
            codex_processes.pop(task_id, None)
    return process.returncode or 1, stdout or "", stderr or "", reason


async def process_task(task_id: str) -> None:
    task_dir = RUNS_DIR / task_id
    request_path = task_dir / "request.txt"
    request_text = request_path.read_text(encoding="utf-8").strip()
    started = datetime.now(timezone.utc).isoformat()
    branch = ensure_task_branch(task_id)
    task_store.update_meta(task_id, branch=branch)
    task_store.update_meta(task_id, status="RUNNING", started_at=started)
    return_code, stdout_capture, stderr_capture, reason = _run_codex(task_id, request_text)
    stdout_text = mask_sensitive(stdout_capture or _build_stdout_text(task_id, request_text))
    stderr_text = mask_sensitive(stderr_capture or "")
    (task_dir / "stdout.log").write_text(stdout_text, encoding="utf-8")
    (task_dir / "stderr.log").write_text(stderr_text, encoding="utf-8")
    stderr_sample = stderr_text.strip().splitlines()[:3]
    stderr_excerpt = " | ".join(stderr_sample) if stderr_sample else "없음"
    current_meta = load_task_meta(task_id)
    if current_meta.get("status") == "CANCELED":
        canceled_summary = mask_sensitive(
            f"Task {task_id}이(가) 사용자 취소로 종료되었습니다 (reason={reason or 'cancelled'})."
        )
        (task_dir / "summary.md").write_text(canceled_summary, encoding="utf-8")
        task_store.update_meta(
            task_id,
            finished_at=datetime.now(timezone.utc).isoformat(),
            notes="사용자 취소",
        )
        return
    diff_text = generate_git_diff(branch)
    diff_path = task_dir / "diff.patch"
    diff_exists = bool(diff_text.strip())
    if diff_exists:
        diff_path.write_text(diff_text, encoding="utf-8")
    elif diff_path.exists():
        diff_path.unlink()
    execution_note = reason or "정상"
    summary_text = _build_summary_text(
        task_id, request_text, return_code, stderr_excerpt, diff_exists, execution_note
    )
    masked_summary = mask_sensitive(summary_text)
    (task_dir / "summary.md").write_text(masked_summary, encoding="utf-8")
    task_store.update_meta(
        task_id,
        status="READY_TO_APPLY",
        ready_at=datetime.now(timezone.utc).isoformat(),
        return_code=return_code,
        stderr_excerpt=stderr_excerpt,
        diff_exists=diff_exists,
        diff_path=str(diff_path) if diff_exists else None,
        notes="PR3 Codex 실행 완료",
        execution_note=execution_note,
    )


async def queue_worker() -> None:
    try:
        while True:
            try:
                task_id = await task_store.queue.get()
            except asyncio.CancelledError:
                logger.info("큐 워커가 취소되어 종료 중")
                break
            meta = load_task_meta(task_id)
            if meta.get("status") == "CANCELED":
                task_store.queue.task_done()
                continue
            try:
                logger.info("큐 워커가 작업 %s 실행", task_id)
                await process_task(task_id)
            except Exception:
                logger.exception("작업 %s 처리 중 오류", task_id)
                task_store.update_meta(task_id, status="FAILED", notes="큐 처리 중 예외")
            finally:
                task_store.queue.task_done()
    except asyncio.CancelledError:
        logger.info("큐 워커 루프가 취소됨")


async def start_queue_worker(application: "telegram.ext.Application") -> None:
    worker = application.create_task(queue_worker())
    application.bot_data["queue_worker_task"] = worker


async def stop_queue_worker(application: "telegram.ext.Application") -> None:
    worker = application.bot_data.pop("queue_worker_task", None)
    if not worker:
        return
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        logger.info("큐 워커를 정상적으로 취소했습니다.")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    config = load_configuration()
    token = config.get("token")
    allowed = config.get("allowed_user_ids") or []
    if not token:
        raise SystemExit("telegram token이 없습니다. config/telegram.yaml을 확인하세요.")
    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(start_queue_worker)
        .post_shutdown(stop_queue_worker)
        .build()
    )
    allowed_ids = set(allowed)

    def guard(handler):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if not update.effective_user or update.effective_user.id not in allowed_ids:
                await _not_allowed(update)
                return
            await handler(update, context)

        return wrapper

    app.add_handler(CommandHandler("ping", guard(ping)))
    app.add_handler(CommandHandler("help", guard(help_command)))
    app.add_handler(CommandHandler("status", guard(status_command)))
    app.add_handler(CommandHandler("diff", guard(diff_command)))
    app.add_handler(CommandHandler("logs", guard(logs_command)))
    app.add_handler(CommandHandler("cancel", guard(cancel_command)))
    app.add_handler(CommandHandler("apply", guard(apply_command)))
    app.add_handler(CommandHandler("commit", guard(commit_command)))
    app.add_handler(CommandHandler("merge", guard(merge_command)))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, guard(natural_text_handler))
    )

    logger.info("Bot polling을 시작합니다. allowlist 크기=%s", len(allowed_ids))
    app.run_polling()


if __name__ == "__main__":
    main()
