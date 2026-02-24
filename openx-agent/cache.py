"""TTL cache for GitHub API responses to reduce rate-limit and latency.

Improvements over the previous version
---------------------------------------
- O(1) LRU eviction via `collections.OrderedDict` (was O(n) `min()` scan).
- Per-entry TTL stored alongside the value so `cached_list` actually respects
  the caller-supplied TTL (was always using the cache-level default).
- All three caches are eagerly initialised at module load — no redundant
  None-checks or factory functions.
- `purge_expired()` is called lazily during `set()` once the store reaches 80%
  capacity, keeping memory use bounded without a background thread.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# Default TTLs (seconds)
CACHE_TTL_REPO = 120
CACHE_TTL_LIST = 60
CACHE_TTL_PR = 90


class TTLCache:
    """Thread-safe TTL cache with O(1) LRU eviction."""

    def __init__(self, default_ttl: float, max_size: int = 500):
        self._default_ttl = default_ttl
        self._max_size = max_size
        # OrderedDict preserves insertion order; oldest entries are at the front.
        # Value format: (data, expiry_timestamp)
        self._data: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self._data:
                return None
            val, expiry = self._data[key]
            if time.monotonic() > expiry:
                del self._data[key]
                return None
            # Move to end to mark as recently used.
            self._data.move_to_end(key)
            return val

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        effective_ttl = ttl if ttl is not None else self._default_ttl
        expiry = time.monotonic() + effective_ttl
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self._data[key] = (value, expiry)
                return
            # Purge expired entries when approaching capacity (80% threshold)
            # to avoid unnecessary eviction of still-valid entries.
            if len(self._data) >= int(self._max_size * 0.8):
                self._purge_expired_locked()
            # Still at capacity after purge — evict the oldest entry (O(1)).
            if len(self._data) >= self._max_size:
                self._data.popitem(last=False)
            self._data[key] = (value, expiry)

    def _purge_expired_locked(self) -> None:
        """Remove all expired entries. Must be called with `_lock` held."""
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._data.items() if now > exp]
        for k in expired:
            del self._data[k]

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


# ---------------------------------------------------------------------------
# Module-level eagerly-initialised caches (no lazy None-check factory needed)
# ---------------------------------------------------------------------------

_repo_cache = TTLCache(CACHE_TTL_REPO)
_list_cache = TTLCache(CACHE_TTL_LIST)
_pr_cache = TTLCache(CACHE_TTL_PR)


def cached_repo(full_name: str, fetcher: Callable[[], T]) -> T:
    """Return cached repo or call fetcher and cache result."""
    key = f"repo:{full_name}"
    out = _repo_cache.get(key)
    if out is not None:
        return out  # type: ignore[return-value]
    out = fetcher()
    _repo_cache.set(key, out)
    return out  # type: ignore[return-value]


def cached_list(cache_key: str, ttl: float, fetcher: Callable[[], T]) -> T:
    """Generic cached list (e.g. list_prs, list_repos).

    The `ttl` argument is now respected — each entry is stored with its own
    expiry, so different callers can supply different TTLs.
    """
    out = _list_cache.get(cache_key)
    if out is not None:
        return out  # type: ignore[return-value]
    out = fetcher()
    _list_cache.set(cache_key, out, ttl=ttl)
    return out  # type: ignore[return-value]


def cached_pr(repo_full_name: str, number: int, fetcher: Callable[[], T]) -> T:
    """Return cached get_pr result or fetch and cache."""
    key = f"pr:{repo_full_name}:{number}"
    out = _pr_cache.get(key)
    if out is not None:
        return out  # type: ignore[return-value]
    out = fetcher()
    _pr_cache.set(key, out)
    return out  # type: ignore[return-value]


def clear_caches() -> None:
    """Clear all caches (e.g. after long-running write operations)."""
    _repo_cache.clear()
    _list_cache.clear()
    _pr_cache.clear()
