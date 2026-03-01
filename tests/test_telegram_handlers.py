from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from dogfoot.interfaces.telegram.context import TelegramRuntime
from dogfoot.interfaces.telegram.project_handlers import (
    project_clone_command,
    project_create_command,
    project_list_command,
    status_command,
    project_use_command,
)
from dogfoot.interfaces.telegram.task_handlers import cancel_command
from dogfoot.interfaces.telegram.task_handlers import new_command, natural_text_handler
from dogfoot.tasks.models import Status


def _make_update() -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(reply_text=AsyncMock(), reply_document=AsyncMock()))


def _make_context(args: list[str]) -> SimpleNamespace:
    return SimpleNamespace(args=args)


def _make_runtime() -> TelegramRuntime:
    active_project = SimpleNamespace(name="alpha", project_root="/tmp/alpha")
    return TelegramRuntime(
        bot=None,
        project_manager=SimpleNamespace(
            list_projects=lambda: ["alpha", "beta"],
            set_active_project=lambda name: None,
            create_project=lambda name, template="empty": SimpleNamespace(name=name, project_root=f"/tmp/{name}"),
            clone_project=lambda name, repo_url, branch=None: SimpleNamespace(name=name, project_root=f"/tmp/{name}"),
            get_active_project=lambda: active_project,
            system_config=SimpleNamespace(active_project="alpha"),
        ),
        task_store=SimpleNamespace(
            load_task_meta=lambda task_id: {"status": Status.QUEUED},
            update_meta=lambda *args, **kwargs: None,
            latest_session_id_for_project=lambda project_name: "session-1",
            create_task_with_session=lambda *args, **kwargs: "task-1",
            status_summary=lambda: "RUNNING: 0\nQUEUED: 0\n최근 완료: 0",
        ),
        git_client=SimpleNamespace(),
        codex_runner=SimpleNamespace(cancel=lambda task_id: True),
        task_runner=SimpleNamespace(),
        notifier=AsyncMock(),
        project_loader=lambda meta: None,
        config_dir=None,
    )


@pytest.mark.integration
def test_project_list_handler_reports_projects() -> None:
    runtime = _make_runtime()
    update = _make_update()

    asyncio.run(project_list_command(runtime, update, _make_context([])))

    update.message.reply_text.assert_awaited_once()
    assert "alpha" in update.message.reply_text.await_args.args[0]
    assert "alpha *" in update.message.reply_text.await_args.args[0]


@pytest.mark.integration
def test_project_use_handler_requires_name() -> None:
    runtime = _make_runtime()
    update = _make_update()

    asyncio.run(project_use_command(runtime, update, _make_context([])))

    update.message.reply_text.assert_awaited_once()
    assert "/project_use <name>" in update.message.reply_text.await_args.args[0]


@pytest.mark.integration
def test_project_create_handler_reports_created_project() -> None:
    runtime = _make_runtime()
    update = _make_update()

    asyncio.run(project_create_command(runtime, update, _make_context(["gamma", "python"])))

    update.message.reply_text.assert_awaited_once()
    assert "gamma" in update.message.reply_text.await_args.args[0]


@pytest.mark.integration
def test_project_clone_handler_reports_cloned_project() -> None:
    runtime = _make_runtime()
    update = _make_update()

    asyncio.run(project_clone_command(runtime, update, _make_context(["delta", "https://example.com/repo.git"])))

    update.message.reply_text.assert_awaited_once()
    assert "delta" in update.message.reply_text.await_args.args[0]


@pytest.mark.integration
def test_status_handler_reports_active_project_and_latest_session() -> None:
    runtime = _make_runtime()
    update = _make_update()

    asyncio.run(status_command(runtime, update, _make_context([])))

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.await_args.args[0]
    assert "ACTIVE_PROJECT: alpha" in text
    assert "PROJECT_ROOT: /tmp/alpha" in text
    assert "LATEST_SESSION: session-1" in text


@pytest.mark.integration
def test_cancel_handler_updates_running_task() -> None:
    updates: list[tuple[tuple, dict]] = []
    runtime = _make_runtime()
    runtime.task_store = SimpleNamespace(
        load_task_meta=lambda task_id: {"status": Status.RUNNING},
        update_meta=lambda *args, **kwargs: updates.append((args, kwargs)),
    )
    update = _make_update()

    asyncio.run(cancel_command(runtime, update, _make_context(["task-1"])))

    assert updates
    update.message.reply_text.assert_awaited_once()
    assert "취소" in update.message.reply_text.await_args.args[0]


@pytest.mark.integration
def test_natural_text_handler_uses_resume_session_when_available() -> None:
    captured: dict = {}
    runtime = _make_runtime()
    runtime.task_store = SimpleNamespace(
        latest_session_id_for_project=lambda project_name: "session-1",
        create_task_with_session=lambda *args, **kwargs: captured.update(
            {"args": args, "kwargs": kwargs}
        )
        or "task-1",
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=7),
        effective_chat=SimpleNamespace(id=8),
        message=SimpleNamespace(text="continue work", reply_text=AsyncMock(), reply_document=AsyncMock()),
    )

    asyncio.run(natural_text_handler(runtime, update, _make_context([])))

    assert captured["kwargs"]["session_mode"] == "resume"
    assert captured["kwargs"]["session_id"] == "session-1"


@pytest.mark.integration
def test_new_command_forces_new_session() -> None:
    captured: dict = {}
    runtime = _make_runtime()
    runtime.task_store = SimpleNamespace(
        latest_session_id_for_project=lambda project_name: "session-1",
        create_task_with_session=lambda *args, **kwargs: captured.update(
            {"args": args, "kwargs": kwargs}
        )
        or "task-2",
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=7),
        effective_chat=SimpleNamespace(id=8),
        message=SimpleNamespace(reply_text=AsyncMock(), reply_document=AsyncMock()),
    )

    asyncio.run(new_command(runtime, update, _make_context(["fresh", "start"])))

    assert captured["kwargs"]["session_mode"] == "new"
    assert captured["kwargs"]["session_id"] is None


@pytest.mark.integration
def test_natural_text_handler_reports_missing_active_project() -> None:
    runtime = _make_runtime()
    runtime.project_manager = SimpleNamespace(
        system_config=SimpleNamespace(active_project=None),
        get_active_project=lambda: (_ for _ in ()).throw(ValueError("No active project configured")),
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=7),
        effective_chat=SimpleNamespace(id=8),
        message=SimpleNamespace(text="continue work", reply_text=AsyncMock(), reply_document=AsyncMock()),
    )

    asyncio.run(natural_text_handler(runtime, update, _make_context([])))

    update.message.reply_text.assert_awaited_once()
    assert "/project_use <name>" in update.message.reply_text.await_args.args[0]
