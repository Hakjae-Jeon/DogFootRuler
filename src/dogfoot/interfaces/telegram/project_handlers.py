from __future__ import annotations

from pathlib import Path

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
        "/project_clone <name> <repo_url> [branch]",
        "/project_remove <name> [--force]",
        "/project_root show",
        "/project_root set <path> [--migrate]",
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
    recovered_name, recovery_reason = runtime.project_manager.recover_active_project()
    active_project_name = runtime.project_manager.system_config.active_project or "(none)"
    active_lines = [f"ACTIVE_PROJECT: {active_project_name}"]
    if recovered_name:
        active_lines.append(f"ACTIVE_PROJECT_STATUS: cleared ({recovered_name}: {recovery_reason})")
        active_lines.append("복구: /project_list 후 /project_use <name>")
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
    recovered_name, recovery_reason = runtime.project_manager.recover_active_project()
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
    if recovered_name:
        text += f"\nactive_project가 해제되었습니다: {recovered_name} ({recovery_reason})"
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


async def project_clone_command(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("/project_clone <name> <repo_url> [branch] 형식으로 입력하세요.")
        return
    name = context.args[0]
    repo_url = context.args[1]
    branch = context.args[2] if len(context.args) > 2 else None
    try:
        project = runtime.project_manager.clone_project(name, repo_url, branch=branch)
    except Exception as exc:
        await update.message.reply_text(f"프로젝트 clone 실패: {exc}")
        return
    await update.message.reply_text(
        f"프로젝트 {project.name} clone 완료: {project.project_root}\n/project_use {project.name} 로 활성화하세요."
    )


async def project_remove_command(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not context.args:
        await update.message.reply_text("/project_remove <name> [--force] 형식으로 입력하세요.")
        return
    name = context.args[0]
    force = any(arg == "--force" for arg in context.args[1:])

    active_statuses = {"QUEUED", "RUNNING"}
    project_task_ids = [
        task_id
        for task_id, meta in runtime.task_store.tasks.items()
        if meta.get("project_name") == name and meta.get("status") in active_statuses
    ]
    if project_task_ids and not force:
        await update.message.reply_text(
            f"진행 중 task가 있어 제거할 수 없습니다: {', '.join(project_task_ids[:5])}\n--force를 사용하면 취소 후 제거합니다."
        )
        return

    if force:
        for task_id in project_task_ids:
            meta = runtime.task_store.load_task_meta(task_id)
            status = meta.get("status")
            if status == "RUNNING":
                runtime.codex_runner.cancel(task_id)
            runtime.task_store.update_meta(
                task_id,
                status="CANCELED",
                notes="프로젝트 제거(--force)로 취소",
            )

    try:
        destination, removed_active = runtime.project_manager.remove_project(name, force_delete=force)
    except Exception as exc:
        await update.message.reply_text(f"프로젝트 제거 실패: {exc}")
        return

    if force:
        message = f"프로젝트 {name}을(를) 영구 삭제했습니다: {destination}"
    else:
        message = f"프로젝트 {name}을(를) trash로 이동했습니다: {destination}"
    if removed_active:
        message += "\nactive_project는 해제되었습니다."
    await update.message.reply_text(message)


async def project_root_command(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not context.args:
        await update.message.reply_text("/project_root show | /project_root set <path> [--migrate]")
        return

    subcommand = context.args[0]
    if subcommand == "show":
        await update.message.reply_text(f"project_base_root: {runtime.project_manager.project_base_root}")
        return

    if subcommand == "set":
        if len(context.args) < 2:
            await update.message.reply_text("/project_root set <path> [--migrate] 형식으로 입력하세요.")
            return
        target = context.args[1]
        migrate = any(arg == "--migrate" for arg in context.args[2:])
        try:
            previous_root, migrated_projects = runtime.project_manager.set_project_base_root(Path(target), migrate=migrate)
        except Exception as exc:
            await update.message.reply_text(f"project_root 변경 실패: {exc}")
            return
        message = (
            f"project_base_root 변경 완료:\nold={previous_root}\nnew={runtime.project_manager.project_base_root}"
        )
        if migrated_projects:
            message += f"\nmigrated: {', '.join(migrated_projects)}"
        await update.message.reply_text(message)
        return

    await update.message.reply_text("/project_root show | /project_root set <path> [--migrate]")
