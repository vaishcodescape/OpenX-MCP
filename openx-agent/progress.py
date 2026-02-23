"""Progress reporting for long-running operations (heal_ci, index)."""

from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_state: dict[str, Any] = {}


def set_progress(operation: str, stage: str, message: str, extra: dict[str, Any] | None = None) -> None:
    with _lock:
        _state[operation] = {
            "operation": operation,
            "stage": stage,
            "message": message,
            "extra": extra or {},
            "updated_at": time.time(),
        }


def get_progress(operation: str | None = None) -> dict[str, Any] | None:
    """Return latest progress for operation, or for any operation if operation is None."""
    with _lock:
        if operation:
            return _state.get(operation)
        if not _state:
            return None
        return max(_state.values(), key=lambda x: x["updated_at"])


def clear_progress(operation: str) -> None:
    with _lock:
        _state.pop(operation, None)
