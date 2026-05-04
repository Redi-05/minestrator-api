from __future__ import annotations

from datetime import datetime
from typing import Any


def parse_int(value: Any, default: int = 0) -> int:
    """Convert API values to int safely."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return int(text)
        except ValueError:
            return default
    return default


def parse_float(value: Any, default: float = 0.0) -> float:
    """Convert API values to float safely."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return float(text)
        except ValueError:
            return default
    return default


def parse_bool(value: Any, default: bool = False) -> bool:
    """Convert API values to bool safely."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "y", "on"}:
            return True
        if text in {"false", "0", "no", "n", "off"}:
            return False
    return default


def normalize_remote_path(path: str) -> str:
    """Normalize remote path for files endpoints."""
    return str(path).replace("\\", "/").strip().lstrip("/")


def format_stats_timestamp(value: str | datetime) -> str:
    """Normalize stats endpoint timestamp components."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%S")
    return str(value).strip()
