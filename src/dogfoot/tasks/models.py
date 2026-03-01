from __future__ import annotations

from typing import Any


class Status:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    READY_TO_APPLY = "READY_TO_APPLY"
    APPLIED = "APPLIED"
    COMMITTED = "COMMITTED"
    MERGED = "MERGED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    ALL = {
        QUEUED,
        RUNNING,
        READY_TO_APPLY,
        APPLIED,
        COMMITTED,
        MERGED,
        FAILED,
        CANCELED,
    }


STATUS_ALIASES: dict[str, str] = {"DONE": Status.READY_TO_APPLY}


def canonical_status(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    key = raw.strip().upper()
    normalized = STATUS_ALIASES.get(key, key)
    return normalized if normalized in Status.ALL else None
