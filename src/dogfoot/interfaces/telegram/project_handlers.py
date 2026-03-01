from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from dogfoot.interfaces.telegram.context import TelegramRuntime


async def help_command(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    commands = [
        "/ping",
        "/help",
        "/status",
        "/project_list",
        "/project_use <name>",
        "/project_create <name> [template]",
        "/new <prompt>",
        "/logs <task_id>",
        "/commit <task_id> <message>",
        "자연어 작업 요청",
    ]
    if update.message:
        await update.message.reply_text("사용 가능한 명령:\n" + "\n".join(commands))


async def status_command(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    summary = runtime.task_store.status_summary()
    active_project_name = runtime.project_manager.system_config.active_project or "(none)"
    active_lines = [f"ACTIVE_PROJECT: {active_project_name}"]
    if runtime.project_manager.system_config.active_project:
        try:
            active_project = runtime.project_manager.get_active_project()
            latest_session_id = runtime.task_store.latest_session_id_for_project(active_project.name)
            active_lines.append(f"PROJECT_ROOT: {active_project.project_root}")
            active_lines.append(f"LATEST_SESSION: {latest_session_id or '(none)'}")
        except Exception as exc:
            active_lines.append(f"ACTIVE_PROJECT_STATUS: invalid ({exc})")
            active_lines.append("복구: /project_list 후 /project_use <name>")
    else:
        active_lines.append("복구: /project_list 또는 /project_create <name> [template]")
    if update.message:
        await update.message.reply_text("\n".join(active_lines + [summary]))


async def project_list_command(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    projects = runtime.project_manager.list_projects()
    active_project_name = runtime.project_manager.system_config.active_project or "(none)"
    if not projects:
        text = f"등록된 프로젝트가 없습니다. active={active_project_name}"
    else:
        lines = []
        for name in projects:
            suffix = " *" if name == active_project_name else ""
            lines.append(f"{name}{suffix}")
        text = "프로젝트 목록:\n" + "\n".join(lines) + f"\nactive={active_project_name}"
    await update.message.reply_text(text)


async def project_use_command(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not context.args:
        await update.message.reply_text("/project_use <name> 형식으로 입력하세요.")
        return
    name = context.args[0]
    try:
        runtime.project_manager.set_active_project(name)
    except Exception as exc:
        await update.message.reply_text(f"프로젝트 선택 실패: {exc}")
        return
    await update.message.reply_text(f"active_project가 {name}으로 변경되었습니다. 새 task부터 적용됩니다.")


async def project_create_command(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not context.args:
        await update.message.reply_text("/project_create <name> [empty|python|node] 형식으로 입력하세요.")
        return
    name = context.args[0]
    template = context.args[1] if len(context.args) > 1 else "empty"
    try:
        project = runtime.project_manager.create_project(name, template=template)
    except Exception as exc:
        await update.message.reply_text(f"프로젝트 생성 실패: {exc}")
        return
    await update.message.reply_text(
        f"프로젝트 {project.name} 생성 완료: {project.project_root}\n/project_use {project.name} 로 활성화하세요."
    )
