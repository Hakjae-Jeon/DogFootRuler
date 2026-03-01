from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Match
from zipfile import ZipFile


MaskRule = tuple[re.Pattern[str], Callable[[Match[str]], str]]
MASK_RULES: list[MaskRule] = [
    (
        re.compile(r"(?i)(token|key|secret)\s*[:=]\s*([^\s,;]+)"),
        lambda m: f"{m.group(1)}***",
    ),
    (
        re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-_.=]+"),
        lambda _: "Bearer ***",
    ),
    (
        re.compile(r"sk-[A-Za-z0-9]{32,}", re.IGNORECASE),
        lambda _: "sk-***",
    ),
    (
        re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(?:\"[^\"]*\"|'[^']*'|[^\s]+)"),
        lambda m: f"{m.group(1)}=***",
    ),
]

LOG_ARCHIVE_NAME = "artifacts.zip"


def mask_sensitive(text: str) -> str:
    masked = text
    for pattern, handler in MASK_RULES:
        masked = pattern.sub(handler, masked)
    return masked


def create_artifacts_zip(task_dir: Path) -> Path:
    zip_path = task_dir / LOG_ARCHIVE_NAME
    files_to_zip = ["request.txt", "stdout.log", "stderr.log", "summary.md", "diff.patch"]
    with ZipFile(zip_path, "w") as archive:
        for name in files_to_zip:
            source = task_dir / name
            if source.exists():
                archive.write(source, arcname=name)
    return zip_path


def build_stdout_text(task_id: str, request: str) -> str:
    return (
        f"Task {task_id} 실행 시작\n"
        f"요청: {request[:200]}\n"
        f"시간: {datetime.now(timezone.utc).isoformat()}\n"
    )


def build_summary_text(
    task_id: str,
    project_name: str,
    request: str,
    return_code: int,
    stderr_sample: str,
    diff_exists: bool,
    execution_note: str,
) -> str:
    status_text = "성공" if return_code == 0 else "실패"
    return (
        f"Task {task_id} 처리 결과: {status_text}\n"
        f"프로젝트: {project_name}\n"
        f"원본 요청: {request}\n"
        f"다음 단계: /diff {task_id}, /logs {task_id}\n"
        f"Codex 명령: codex exec \"{request}\"\n"
        f"stderr 요약: {stderr_sample}\n"
        f"Diff 생성 여부: {'있음' if diff_exists else '없음'}\n"
        f"실행 노트: {execution_note}\n"
    )
