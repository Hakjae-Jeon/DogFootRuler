from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from dogfoot.application.artifacts import create_artifacts_zip
from dogfoot.application.task_runner import TaskRunner
from dogfoot.config.system import SystemConfig
from dogfoot.integrations.codex_runner import CodexRunner
from dogfoot.integrations.git_client import GitClient
from dogfoot.project.manager import ProjectManager
from dogfoot.project.policy import PolicyViolation
from dogfoot.project.project import Project
from dogfoot.tasks.models import Status
from dogfoot.tasks.store import TaskStore
from dogfoot.utils.simple_yaml import load_simple_yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"
LEGACY_RUNS_DIR = REPO_ROOT / "runs"
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
CODEX_TIMEOUT = 180

telegram_bot_client: Bot | None = None
project_manager: ProjectManager | None = None
task_store: TaskStore | None = None
git_client: GitClient | None = None
codex_runner: CodexRunner | None = None
task_runner: TaskRunner | None = None
logger = logging.getLogger(__name__)


def require_project_manager() -> ProjectManager:
    if not project_manager:
        raise RuntimeError("ProjectManager가 초기화되지 않았습니다.")
    return project_manager


def require_task_store() -> TaskStore:
    if not task_store:
        raise RuntimeError("TaskStore가 초기화되지 않았습니다.")
    return task_store


def require_git_client() -> GitClient:
    if not git_client:
        raise RuntimeError("GitClient가 초기화되지 않았습니다.")
    return git_client


def require_codex_runner() -> CodexRunner:
    if not codex_runner:
        raise RuntimeError("CodexRunner가 초기화되지 않았습니다.")
    return codex_runner


def require_task_runner() -> TaskRunner:
    if not task_runner:
        raise RuntimeError("TaskRunner가 초기화되지 않았습니다.")
    return task_runner


def load_project_from_meta(meta: dict[str, Any]) -> Project:
    root = meta.get("project_root")
    if not root:
        raise ValueError("task meta에 project_root가 없습니다.")
    manager = require_project_manager()
    system_config: SystemConfig = manager.system_config
    return Project.load(
        Path(str(root)),
        system_forbidden_subpaths=system_config.system_forbidden_subpaths,
        hard_deny_subpaths=system_config.hard_deny_subpaths,
    )


def load_configuration() -> dict[str, Any]:
    token_conf = load_simple_yaml(CONFIG_DIR / "telegram.yaml")
    allowed_conf = load_simple_yaml(CONFIG_DIR / "allowed_users.yaml")
    allowed = allowed_conf.get("allowed_user_ids") or []
    allowed_ids = [int(v) for v in allowed if isinstance(v, (int, str))]
    return {
        "token": token_conf.get("token"),
        "allowed_user_ids": allowed_ids,
        "system_config_path": CONFIG_DIR / "system.yaml",
    }


async def notify_task_completion(task_id: str, text: str) -> None:
    if not telegram_bot_client:
        return
    meta = require_task_store().load_task_meta(task_id)
    if not meta:
        return
    chat_id = meta.get("chat_id")
    if not chat_id:
        return
    safe_text = text if len(text) <= 4000 else text[:3997] + "..."
    try:
        await telegram_bot_client.send_message(chat_id=chat_id, text=safe_text)
    except Exception:
        logger.exception("Task %s 완료 푸시 실패", task_id)


async def _not_allowed(update: Update) -> None:
    if update.message:
        await update.message.reply_text("권한이 없습니다. allowlist에 Telegram user_id를 추가하세요.")


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text("pong")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    commands = [
        "/ping",
        "/help",
        "/status",
        "/project_list",
        "/project_use <name>",
        "/project_create <name> [template]",
        "자연어 작업 요청",
    ]
    if update.message:
        await update.message.reply_text("사용 가능한 명령:\n" + "\n".join(commands))


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    manager = require_project_manager()
    active_project_name = manager.system_config.active_project or "(none)"
    summary = require_task_store().status_summary()
    if update.message:
        await update.message.reply_text(f"ACTIVE_PROJECT: {active_project_name}\n{summary}")


async def project_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    manager = require_project_manager()
    projects = manager.list_projects()
    active_project_name = manager.system_config.active_project or "(none)"
    if not projects:
        text = f"등록된 프로젝트가 없습니다. active={active_project_name}"
    else:
        text = "프로젝트 목록:\n" + "\n".join(projects) + f"\nactive={active_project_name}"
    await update.message.reply_text(text)


async def project_use_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("/project_use <name> 형식으로 입력하세요.")
        return
    name = context.args[0]
    try:
        require_project_manager().set_active_project(name)
    except Exception as exc:
        await update.message.reply_text(f"프로젝트 선택 실패: {exc}")
        return
    await update.message.reply_text(f"active_project가 {name}으로 변경되었습니다. 새 task부터 적용됩니다.")


async def project_create_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("/project_create <name> [empty|python|node] 형식으로 입력하세요.")
        return
    name = context.args[0]
    template = context.args[1] if len(context.args) > 1 else "empty"
    try:
        project = require_project_manager().create_project(name, template=template)
    except Exception as exc:
        await update.message.reply_text(f"프로젝트 생성 실패: {exc}")
        return
    await update.message.reply_text(
        f"프로젝트 {project.name} 생성 완료: {project.project_root}\n/project_use {project.name} 로 활성화하세요."
    )


async def diff_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("/diff <task_id> 형식으로 요청해주세요.")
        return
    task_id = context.args[0]
    store = require_task_store()
    meta = store.load_task_meta(task_id)
    if not meta:
        await update.message.reply_text(f"{task_id} 메타가 없습니다.")
        return
    task_dir = store.resolve_task_dir(task_id)
    if not task_dir:
        await update.message.reply_text(f"{task_id} 디렉토리를 찾을 수 없습니다.")
        return
    diff_path = task_dir / "diff.patch"
    branch = meta.get("branch") or f"dfr/task/{task_id}"
    if not diff_path.exists() or diff_path.stat().st_size == 0:
        await update.message.reply_text(f"{task_id}에 대한 diff가 생성되지 않았거나 변경 없음.")
        return
    await update.message.reply_text(f"{task_id} ({branch}) diff.patch 첨부합니다.")
    with diff_path.open("rb") as fh:
        await update.message.reply_document(document=fh, filename=f"{task_id}-diff.patch")


async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("/logs <task_id>로 artifact zip을 받아보세요.")
        return
    task_id = context.args[0]
    task_dir = require_task_store().resolve_task_dir(task_id)
    if not task_dir:
        await update.message.reply_text(f"{task_id} 디렉토리를 찾을 수 없습니다.")
        return
    zip_path = create_artifacts_zip(task_dir)
    if not zip_path.exists() or zip_path.stat().st_size == 0:
        await update.message.reply_text(f"{task_id}에 로그가 생성되지 않았습니다.")
        return
    await update.message.reply_text(f"{task_id} 로그 아카이브를 전송합니다.")
    with zip_path.open("rb") as fh:
        await update.message.reply_document(document=fh, filename=f"{task_id}-artifacts.zip")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("/cancel <task_id>로 큐/실행을 취소하세요.")
        return
    task_id = context.args[0]
    store = require_task_store()
    meta = store.load_task_meta(task_id)
    if not meta:
        await update.message.reply_text(f"{task_id} 메타가 없습니다.")
        return
    status = meta.get("status")
    if status == Status.QUEUED:
        store.update_meta(
            task_id,
            status=Status.CANCELED,
            notes="사용자 취소(큐)",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        await update.message.reply_text(f"{task_id}을(를) 큐에서 취소했습니다.")
        return
    if status == Status.RUNNING:
        if require_codex_runner().cancel(task_id):
            store.update_meta(
                task_id,
                status=Status.CANCELED,
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
    store = require_task_store()
    meta = store.load_task_meta(task_id)
    if not meta:
        await update.message.reply_text(f"{task_id} 메타가 없습니다.")
        return
    if meta.get("status") != Status.READY_TO_APPLY:
        await update.message.reply_text(f"{task_id} 상태가 {meta.get('status')}라 적용할 수 없습니다.")
        return
    task_dir = store.resolve_task_dir(task_id)
    if not task_dir:
        await update.message.reply_text(f"{task_id} 디렉토리를 찾을 수 없습니다.")
        return
    diff_path = task_dir / "diff.patch"
    if not diff_path.exists():
        await update.message.reply_text(f"{task_id}에 diff가 없습니다.")
        return
    project = load_project_from_meta(meta)
    git = require_git_client()
    if not git.workspace_is_clean(project.project_root):
        await update.message.reply_text("작업 트리가 깨끗해야 합니다. `git status`를 확인하세요.")
        return
    changed_files = list(meta.get("changed_files") or [])
    try:
        project.assert_changes_allowed(changed_files)
    except PolicyViolation as exc:
        store.update_meta(task_id, status=Status.FAILED, notes=str(exc))
        await update.message.reply_text(f"정책 위반으로 적용할 수 없습니다: {exc}")
        return
    branch = meta.get("branch") or git.ensure_task_branch(task_id, project.project_root)
    ok, err = git.checkout_branch(branch, project.project_root)
    if not ok:
        await update.message.reply_text(f"브랜치 체크아웃 실패: {err}")
        return
    apply_result = git.apply_diff_file(diff_path, project.project_root)
    if apply_result.returncode != 0:
        await update.message.reply_text(f"diff 적용 실패: {apply_result.stderr.strip()}")
        return
    git.stage_all(project.project_root)
    store.update_meta(
        task_id,
        status=Status.APPLIED,
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
    store = require_task_store()
    meta = store.load_task_meta(task_id)
    if not meta:
        await update.message.reply_text(f"{task_id} 메타가 없습니다.")
        return
    status = meta.get("status")
    if status == Status.COMMITTED:
        await update.message.reply_text(f"{task_id}은 이미 커밋되었습니다.")
        return
    if status != Status.APPLIED:
        await update.message.reply_text(f"{task_id}이 아직 적용 상태가 아닙니다 (현재 {status}).")
        return
    project = load_project_from_meta(meta)
    changed_files = list(meta.get("changed_files") or [])
    try:
        project.assert_changes_allowed(changed_files)
    except PolicyViolation as exc:
        store.update_meta(task_id, status=Status.FAILED, notes=str(exc))
        await update.message.reply_text(f"정책 위반으로 커밋할 수 없습니다: {exc}")
        return
    git = require_git_client()
    branch = meta.get("branch") or git.ensure_task_branch(task_id, project.project_root)
    ok, err = git.checkout_branch(branch, project.project_root)
    if not ok:
        await update.message.reply_text(f"브랜치 체크아웃 실패: {err}")
        return
    commit_result = git.commit(message, project.project_root)
    if commit_result.returncode != 0:
        await update.message.reply_text(f"커밋 실패: {commit_result.stderr.strip()}")
        return
    store.update_meta(
        task_id,
        status=Status.COMMITTED,
        commit_hash=git.head(project.project_root),
        commit_message=message,
        committed_at=datetime.now(timezone.utc).isoformat(),
        notes="PR5 커밋 완료",
    )
    await update.message.reply_text(f"{task_id} 커밋 완료: {git.head(project.project_root)}")


async def merge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("/merge <task_id>로 main에 병합하세요.")
        return
    task_id = context.args[0]
    store = require_task_store()
    meta = store.load_task_meta(task_id)
    if not meta:
        await update.message.reply_text(f"{task_id} 메타가 없습니다.")
        return
    status = meta.get("status")
    if status == Status.MERGED:
        await update.message.reply_text(f"{task_id}은 이미 main에 병합되었습니다.")
        return
    if status != Status.COMMITTED:
        await update.message.reply_text(f"{task_id}은 커밋되지 않았습니다 (현재 {status}).")
        return
    project = load_project_from_meta(meta)
    changed_files = list(meta.get("changed_files") or [])
    try:
        project.assert_changes_allowed(changed_files)
    except PolicyViolation as exc:
        store.update_meta(task_id, status=Status.FAILED, notes=str(exc))
        await update.message.reply_text(f"정책 위반으로 머지할 수 없습니다: {exc}")
        return
    git = require_git_client()
    branch = meta.get("branch") or git.ensure_task_branch(task_id, project.project_root)
    if not git.workspace_is_clean(project.project_root):
        await update.message.reply_text("main 브랜치를 병합하려면 작업 트리가 깨끗해야 합니다.")
        return
    ok, err = git.checkout_branch(git.main_branch, project.project_root)
    if not ok:
        await update.message.reply_text(f"{git.main_branch} 체크아웃 실패: {err}")
        return
    merge_result = git.merge_no_ff(branch, project.project_root)
    if merge_result.returncode != 0:
        git.merge_abort(project.project_root)
        await update.message.reply_text(
            f"병합 실패: {merge_result.stderr.strip() or merge_result.stdout.strip()}"
        )
        return
    merge_commit = git.head(project.project_root)
    store.update_meta(
        task_id,
        status=Status.MERGED,
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
    try:
        active_project = require_project_manager().get_active_project()
    except Exception as exc:
        await update.message.reply_text(f"active_project를 확인할 수 없습니다: {exc}")
        return
    chat_id = update.effective_chat.id if update.effective_chat else update.effective_user.id
    task_id = require_task_store().create_task(user_id, chat_id, text, active_project)
    queue_size = require_task_store().queue.qsize()
    await update.message.reply_text(
        f"작업 {task_id}이(가) 예약되었습니다. project={active_project.name}, 현재 대기 중: {queue_size}개. /status, /diff, /apply를 확인하세요."
    )


async def start_queue_worker(application: "telegram.ext.Application") -> None:
    worker = application.create_task(require_task_runner().queue_worker())
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
    system_config_path = Path(str(config["system_config_path"]))
    if not system_config_path.exists():
        raise SystemExit("system.yaml이 없습니다. config/system.yaml을 확인하세요.")

    global project_manager, task_store, git_client, codex_runner, task_runner
    project_manager = ProjectManager.load(system_config_path)
    task_store = TaskStore(project_manager, LEGACY_RUNS_DIR)
    git_client = GitClient()
    codex_runner = CodexRunner(timeout=CODEX_TIMEOUT)
    task_runner = TaskRunner(
        task_store=task_store,
        git_client=git_client,
        codex_runner=codex_runner,
        project_loader=load_project_from_meta,
        notifier=notify_task_completion,
        logger=logger,
    )

    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(start_queue_worker)
        .post_shutdown(stop_queue_worker)
        .build()
    )
    global telegram_bot_client
    telegram_bot_client = app.bot
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
    app.add_handler(CommandHandler("project_list", guard(project_list_command)))
    app.add_handler(CommandHandler("project_use", guard(project_use_command)))
    app.add_handler(CommandHandler("project_create", guard(project_create_command)))
    app.add_handler(CommandHandler("diff", guard(diff_command)))
    app.add_handler(CommandHandler("logs", guard(logs_command)))
    app.add_handler(CommandHandler("cancel", guard(cancel_command)))
    app.add_handler(CommandHandler("apply", guard(apply_command)))
    app.add_handler(CommandHandler("commit", guard(commit_command)))
    app.add_handler(CommandHandler("merge", guard(merge_command)))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, guard(natural_text_handler)))

    logger.info("Bot polling을 시작합니다. allowlist 크기=%s", len(allowed_ids))
    app.run_polling()


if __name__ == "__main__":
    main()
