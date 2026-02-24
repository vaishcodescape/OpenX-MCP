"""Thread-safe progress reporting for long-running operations (heal_ci, index).

Callers write via `set_progress`; the FastAPI `/progress` endpoint reads via
`get_progress`. `clear_progress` removes the entry once an operation finishes.
"""

from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_state: dict[str, dict[str, Any]] = {}


def set_progress(
    operation: str,
    stage: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Record the current stage of *operation* (overwrites any previous entry)."""
    with _lock:
        _state[operation] = {
            "operation": operation,
            "stage": stage,
            "message": message,
            "extra": extra or {},
            "updated_at": time.time(),
        }


def get_progress(operation: str | None = None) -> dict[str, Any] | None:
    """Return progress for *operation*, or the most-recently-updated operation if None."""
    with _lock:
        if operation:
            return _state.get(operation)
        return max(_state.values(), key=lambda x: x["updated_at"]) if _state else None


def clear_progress(operation: str) -> None:
    """Remove the progress entry for *operation* (no-op if not present)."""
    with _lock:
        _state.pop(operation, None)
