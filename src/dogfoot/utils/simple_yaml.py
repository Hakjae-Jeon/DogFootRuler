from __future__ import annotations

from pathlib import Path
from typing import Any


def parse_scalar(raw: str) -> Any:
    trimmed = raw.strip()
    if not trimmed:
        return ""
    if trimmed[0] in "'\"" and trimmed.endswith(trimmed[0]) and len(trimmed) >= 2:
        return trimmed[1:-1]
    lowered = trimmed.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if trimmed.startswith("[") and trimmed.endswith("]"):
        inner = trimmed[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",")]
    if trimmed.lstrip("-").isdigit():
        return int(trimmed)
    return trimmed


def load_simple_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data: dict[str, Any] = {}
    current_list_key: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.split("#", 1)[0].strip()
        if not cleaned:
            continue
        if cleaned.startswith("- "):
            if current_list_key:
                data.setdefault(current_list_key, []).append(parse_scalar(cleaned[2:].strip()))
            continue
        if ":" not in cleaned:
            current_list_key = None
            continue
        key, value = map(str.strip, cleaned.split(":", 1))
        if not value:
            data[key] = []
            current_list_key = key
            continue
        parsed = parse_scalar(value)
        data[key] = parsed
        current_list_key = key if isinstance(parsed, list) else None
    return data


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if not text or any(ch in text for ch in ":#[]{}") or text != text.strip():
        return f'"{text}"'
    return text


def dump_simple_yaml(data: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {_format_scalar(item)}")
            if not value:
                lines[-1] = f"{key}: []"
            continue
        lines.append(f"{key}: {_format_scalar(value)}")
    return "\n".join(lines) + "\n"
