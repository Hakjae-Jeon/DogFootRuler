from __future__ import annotations

from pathlib import Path

from dogfoot.integrations.codex_runner import CodexRunner


def test_codex_runner_builds_resume_command() -> None:
    runner = CodexRunner()
    command = runner.build_command("continue work", session_mode="resume", session_id="session-123")
    assert command == ["codex", "exec", "resume", "--full-auto", "session-123", "continue work"]


def test_codex_runner_builds_new_command() -> None:
    runner = CodexRunner()
    command = runner.build_command("start", session_mode="new", session_id=None)
    assert command == ["codex", "exec", "--sandbox", "workspace-write", "start"]


def test_codex_runner_extracts_session_id() -> None:
    runner = CodexRunner()
    stderr_text = "OpenAI Codex\nsession id: 019caa40-3c41-79f0-990d-835e26ae31d0\n"
    assert runner.extract_session_id(stderr_text) == "019caa40-3c41-79f0-990d-835e26ae31d0"
