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
        re.compile(r"(?i)\b([A-Za-z_][A-Za-z0-9_]*(?:token|key|secret|password)[A-Za-z0-9_]*)=(?:\"[^\"]*\"|'[^']*'|[^\s]+)"),
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
                if name == "request.txt":
                    archive.writestr(name, mask_sensitive(source.read_text(encoding="utf-8")))
                else:
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
        f"적용 상태: 작업 트리에 즉시 반영됨 (/apply 불필요)\n"
        f"다음 단계: /logs {task_id}, /commit {task_id} <message>\n"
        f"Codex 명령: codex exec \"{request}\"\n"
        f"stderr 요약: {stderr_sample}\n"
        f"Diff 생성 여부: {'있음' if diff_exists else '없음'}\n"
        f"실행 노트: {execution_note}\n"
    )


def build_failure_summary_text(
    task_id: str,
    project_name: str,
    request: str,
    failure_reason: str,
    stdout_sample: str,
    stderr_sample: str,
    execution_note: str,
) -> str:
    return (
        f"Task {task_id} 처리 결과: 실패\n"
        f"프로젝트: {project_name}\n"
        f"원본 요청: {request}\n"
        f"실패 원인: {failure_reason}\n"
        f"Codex stdout 요약: {stdout_sample}\n"
        f"Codex stderr 요약: {stderr_sample}\n"
        f"다음 단계: /logs {task_id} 로 상세 로그 확인\n"
        f"실행 노트: {execution_note}\n"
    )
