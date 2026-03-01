from __future__ import annotations

from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from dogfoot.application.artifacts import create_artifacts_zip
from dogfoot.interfaces.telegram.context import TelegramRuntime
from dogfoot.project.policy import PolicyViolation
from dogfoot.tasks.models import Status


def _validated_changed_files(runtime: TelegramRuntime, meta: dict, task_id: str) -> list[str]:
    project = runtime.project_loader(meta)
    changed_files = project.policy.normalize_change_paths(meta.get("changed_files") or [])
    project.assert_changes_allowed(changed_files)
    return changed_files


async def logs_command(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not context.args:
        await update.message.reply_text("/logs <task_id>로 artifact zip을 받아보세요.")
        return
    task_id = context.args[0]
    task_dir = runtime.task_store.resolve_task_dir(task_id)
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


async def cancel_command(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not context.args:
        await update.message.reply_text("/cancel <task_id>로 큐/실행을 취소하세요.")
        return
    task_id = context.args[0]
    meta = runtime.task_store.load_task_meta(task_id)
    if not meta:
        await update.message.reply_text(f"{task_id} 메타가 없습니다.")
        return
    status = meta.get("status")
    if status == Status.QUEUED:
        runtime.task_store.update_meta(
            task_id,
            status=Status.CANCELED,
            notes="사용자 취소(큐)",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        await update.message.reply_text(f"{task_id}을(를) 큐에서 취소했습니다.")
        return
    if status == Status.RUNNING:
        if runtime.codex_runner.cancel(task_id):
            runtime.task_store.update_meta(
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


async def apply_command(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not context.args:
        await update.message.reply_text("/apply <task_id>는 더 이상 필요하지 않습니다. 성공한 작업은 즉시 반영됩니다.")
        return
    task_id = context.args[0]
    meta = runtime.task_store.load_task_meta(task_id)
    if not meta:
        await update.message.reply_text(f"{task_id} 메타가 없습니다.")
        return
    status = meta.get("status")
    if status in {Status.APPLIED, Status.COMMITTED}:
        await update.message.reply_text(f"{task_id}은 이미 작업 트리에 반영된 상태입니다 ({status}).")
        return
    await update.message.reply_text(f"{task_id} 상태가 {status}입니다. 자동 반영 모드에서는 수동 /apply를 사용하지 않습니다.")


async def commit_command(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("/commit <task_id> <message> 형식으로 입력하세요.")
        return
    task_id = context.args[0]
    message = " ".join(context.args[1:]).strip()
    if not message:
        await update.message.reply_text("커밋 메시지를 입력하세요.")
        return
    meta = runtime.task_store.load_task_meta(task_id)
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
    try:
        changed_files = _validated_changed_files(runtime, meta, task_id)
    except PolicyViolation as exc:
        runtime.task_store.update_meta(task_id, status=Status.FAILED, notes=str(exc))
        await update.message.reply_text(f"정책 위반으로 커밋할 수 없습니다: {exc}")
        return
    project = runtime.project_loader(meta)
    current_branch = runtime.git_client.current_branch(project.project_root)
    if current_branch != runtime.git_client.main_branch:
        await update.message.reply_text(
            f"자동 반영 모드에서는 {runtime.git_client.main_branch}에서만 커밋합니다. 현재 브랜치: {current_branch}"
        )
        return
    runtime.git_client.stage_all(project.project_root)
    commit_result = runtime.git_client.commit(message, project.project_root)
    if commit_result.returncode != 0:
        await update.message.reply_text(f"커밋 실패: {commit_result.stderr.strip()}")
        return
    head = runtime.git_client.head(project.project_root)
    runtime.task_store.update_meta(
        task_id,
        status=Status.COMMITTED,
        commit_hash=head,
        commit_message=message,
        committed_at=datetime.now(timezone.utc).isoformat(),
        notes="자동 반영된 변경을 main에서 커밋 완료",
    )
    await update.message.reply_text(f"{task_id} 변경을 main에 커밋했습니다: {head}")


async def merge_command(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not context.args:
        await update.message.reply_text("/merge <task_id>는 자동 반영 모드에서 필요하지 않습니다.")
        return
    task_id = context.args[0]
    meta = runtime.task_store.load_task_meta(task_id)
    if not meta:
        await update.message.reply_text(f"{task_id} 메타가 없습니다.")
        return
    await update.message.reply_text(
        f"{task_id}은 이미 {runtime.git_client.main_branch} 작업 트리에 직접 반영되는 방식입니다. /merge는 사용하지 않습니다."
    )


async def natural_text_handler(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    await _enqueue_prompt(runtime, update, update.message.text.strip(), force_new=False)


async def new_command(
    runtime: TelegramRuntime, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    text = " ".join(context.args).strip()
    await _enqueue_prompt(runtime, update, text, force_new=True)


async def _enqueue_prompt(
    runtime: TelegramRuntime,
    update: Update,
    text: str,
    force_new: bool,
) -> None:
    user_id = update.effective_user.id
    if not text:
        await update.message.reply_text("작업 지시를 입력해주세요.")
        return
    try:
        active_project = runtime.project_manager.get_active_project()
    except Exception as exc:
        active_name = runtime.project_manager.system_config.active_project or "(none)"
        if active_name == "(none)":
            await update.message.reply_text(
                "active_project가 없습니다. /project_list로 목록을 보고 /project_use <name>으로 선택하세요."
            )
        else:
            await update.message.reply_text(
                f"active_project({active_name})를 확인할 수 없습니다: {exc}\n복구: /project_list 후 /project_use <name>"
            )
        return
    chat_id = update.effective_chat.id if update.effective_chat else update.effective_user.id
    previous_session_id = None if force_new else runtime.task_store.latest_session_id_for_project(active_project.name)
    session_mode = "resume" if previous_session_id else "new"
    if force_new:
        session_mode = "new"
    task_id = runtime.task_store.create_task_with_session(
        user_id,
        chat_id,
        text,
        active_project,
        session_mode=session_mode,
        session_id=previous_session_id,
    )
