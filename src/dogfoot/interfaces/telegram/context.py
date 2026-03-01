from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from telegram import Bot

from dogfoot.application.task_runner import TaskRunner
from dogfoot.integrations.codex_runner import CodexRunner
from dogfoot.integrations.git_client import GitClient
from dogfoot.project.manager import ProjectManager
from dogfoot.project.project import Project
from dogfoot.tasks.store import TaskStore


@dataclass
class TelegramRuntime:
    bot: Bot | None
    project_manager: ProjectManager
    task_store: TaskStore
    git_client: GitClient
    codex_runner: CodexRunner
    task_runner: TaskRunner
    notifier: Callable[[str, str], Awaitable[None]]
    project_loader: Callable[[dict], Project]
    config_dir: Path
