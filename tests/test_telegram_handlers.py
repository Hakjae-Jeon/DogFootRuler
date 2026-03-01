from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from dogfoot.interfaces.telegram.context import TelegramRuntime
from dogfoot.interfaces.telegram.project_handlers import (
    project_create_command,
    project_list_command,
    project_use_command,
)
from dogfoot.interfaces.telegram.task_handlers import cancel_command
from dogfoot.tasks.models import Status


def _make_update() -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(reply_text=AsyncMock(), reply_document=AsyncMock()))


def _make_context(args: list[str]) -> SimpleNamespace:
    return SimpleNamespace(args=args)


def _make_runtime() -> TelegramRuntime:
    return TelegramRuntime(
        bot=None,
        project_manager=SimpleNamespace(
            list_projects=lambda: ["alpha", "beta"],
            set_active_project=lambda name: None,
            create_project=lambda name, template="empty": SimpleNamespace(name=name, project_root=f"/tmp/{name}"),
            system_config=SimpleNamespace(active_project="alpha"),
        ),
        task_store=SimpleNamespace(
            load_task_meta=lambda task_id: {"status": Status.QUEUED},
            update_meta=lambda *args, **kwargs: None,
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
