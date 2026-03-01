from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from dogfoot.application.startup import validate_manager_startup, validate_system_config_path
from dogfoot.application.task_runner import TaskRunner
from dogfoot.config.system import SystemConfig
from dogfoot.integrations.codex_runner import CodexRunner
from dogfoot.integrations.git_client import GitClient
from dogfoot.interfaces.telegram.context import TelegramRuntime
from dogfoot.interfaces.telegram.project_handlers import (
    help_command,
    project_create_command,
    project_list_command,
    project_use_command,
    status_command,
)
from dogfoot.interfaces.telegram.task_handlers import (
    apply_command,
    cancel_command,
    commit_command,
    diff_command,
    logs_command,
    merge_command,
    natural_text_handler,
)
from dogfoot.project.manager import ProjectManager
from dogfoot.project.project import Project
from dogfoot.tasks.store import TaskStore
from dogfoot.utils.simple_yaml import load_simple_yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"
LEGACY_RUNS_DIR = REPO_ROOT / "runs"
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
CODEX_TIMEOUT = 180

telegram_bot_client: Bot | None = None
runtime: TelegramRuntime | None = None
logger = logging.getLogger(__name__)
TELEGRAM_TEXT_LIMIT = 4000


def require_runtime() -> TelegramRuntime:
    if not runtime:
        raise RuntimeError("Telegram runtime이 초기화되지 않았습니다.")
    return runtime


def load_project_from_meta(meta: dict[str, object]) -> Project:
    root = meta.get("project_root")
    if not root:
        raise ValueError("task meta에 project_root가 없습니다.")
    current_runtime = require_runtime()
    system_config: SystemConfig = current_runtime.project_manager.system_config
    return Project.load(
        Path(str(root)),
        system_forbidden_subpaths=system_config.system_forbidden_subpaths,
        hard_deny_subpaths=system_config.hard_deny_subpaths,
    )


def load_configuration() -> dict[str, object]:
    token_conf = load_simple_yaml(CONFIG_DIR / "telegram.yaml")
    allowed_conf = load_simple_yaml(CONFIG_DIR / "allowed_users.yaml")
    allowed = allowed_conf.get("allowed_user_ids") or []
    allowed_ids = [int(v) for v in allowed if isinstance(v, (int, str))]
    return {
        "token": token_conf.get("token"),
        "allowed_user_ids": allowed_ids,
        "system_config_path": CONFIG_DIR / "system.yaml",
    }


def _split_for_telegram(text: str, limit: int = TELEGRAM_TEXT_LIMIT) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    chunks: list[str] = []
    remaining = stripped
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


async def notify_task_completion(task_id: str, text: str) -> None:
    current_runtime = require_runtime()
    if not current_runtime.bot:
        return
    store = current_runtime.task_store
    meta = store.load_task_meta(task_id)
    if not meta:
        return
    chat_id = meta.get("chat_id")
    if not chat_id:
        return
    task_dir = store.resolve_task_dir(task_id)
    try:
        if task_dir:
            stdout_path = task_dir / "stdout.log"
            if stdout_path.exists():
                stdout_text = stdout_path.read_text(encoding="utf-8").strip()
                if stdout_text:
                    for index, chunk in enumerate(
                        _split_for_telegram(stdout_text)
                    ):
                        prefix = f"[{index + 1}] " if index > 0 else ""
                        await current_runtime.bot.send_message(
                            chat_id=chat_id,
                            text=f"{prefix}{chunk}",
                        )
                    return
            stderr_path = task_dir / "stderr.log"
            if stderr_path.exists():
                stderr_text = stderr_path.read_text(encoding="utf-8").strip()
                if stderr_text:
                    for index, chunk in enumerate(_split_for_telegram(stderr_text)):
                        prefix = f"[{index + 1}] " if index > 0 else ""
                        await current_runtime.bot.send_message(chat_id=chat_id, text=f"{prefix}{chunk}")
                    return
        for chunk in _split_for_telegram(text):
            await current_runtime.bot.send_message(chat_id=chat_id, text=chunk)
    except Exception:
        logger.exception("Task %s 완료 푸시 실패", task_id)


async def _not_allowed(update: Update) -> None:
    if update.message:
        await update.message.reply_text("권한이 없습니다. allowlist에 Telegram user_id를 추가하세요.")


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text("pong")


async def start_queue_worker(application: "telegram.ext.Application") -> None:
    worker = application.create_task(require_runtime().task_runner.queue_worker())
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


def _bind(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await handler(require_runtime(), update, context)

    return wrapper


def main() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    config = load_configuration()
    token = config.get("token")
    allowed = config.get("allowed_user_ids") or []
    if not token:
        raise SystemExit("telegram token이 없습니다. config/telegram.yaml을 확인하세요.")
    try:
        system_config_path = validate_system_config_path(Path(str(config["system_config_path"])))
        project_manager = ProjectManager.load(system_config_path)
        validate_manager_startup(project_manager, require_active_project=False)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        raise SystemExit(str(exc))

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

    global telegram_bot_client, runtime
    telegram_bot_client = app.bot
    runtime = TelegramRuntime(
        bot=app.bot,
        project_manager=project_manager,
        task_store=task_store,
        git_client=git_client,
        codex_runner=codex_runner,
        task_runner=task_runner,
        notifier=notify_task_completion,
        project_loader=load_project_from_meta,
        config_dir=CONFIG_DIR,
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
    app.add_handler(CommandHandler("help", guard(_bind(help_command))))
    app.add_handler(CommandHandler("status", guard(_bind(status_command))))
    app.add_handler(CommandHandler("project_list", guard(_bind(project_list_command))))
    app.add_handler(CommandHandler("project_use", guard(_bind(project_use_command))))
    app.add_handler(CommandHandler("project_create", guard(_bind(project_create_command))))
    app.add_handler(CommandHandler("diff", guard(_bind(diff_command))))
    app.add_handler(CommandHandler("logs", guard(_bind(logs_command))))
    app.add_handler(CommandHandler("cancel", guard(_bind(cancel_command))))
    app.add_handler(CommandHandler("apply", guard(_bind(apply_command))))
    app.add_handler(CommandHandler("commit", guard(_bind(commit_command))))
    app.add_handler(CommandHandler("merge", guard(_bind(merge_command))))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, guard(_bind(natural_text_handler))))

    logger.info("Bot polling을 시작합니다. allowlist 크기=%s", len(allowed_ids))
    app.run_polling()


if __name__ == "__main__":
    main()
