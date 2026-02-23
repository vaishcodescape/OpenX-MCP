"""TTL cache for GitHub API responses to reduce rate-limit and latency."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# Default TTLs (seconds)
CACHE_TTL_REPO = 120
CACHE_TTL_LIST = 60
CACHE_TTL_PR = 90


class TTLCache:
    """Simple thread-safe TTL cache."""

    def __init__(self, ttl_sec: float, max_size: int = 500):
        self._ttl = ttl_sec
        self._max_size = max_size
        self._data: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self._data:
                return None
            val, ts = self._data[key]
            if time.monotonic() - ts > self._ttl:
                del self._data[key]
                return None
            return val

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._data) >= self._max_size:
                # Evict oldest by timestamp (O(n); acceptable for max_size ~500)
                oldest_key = min(self._data.items(), key=lambda x: x[1][1])[0]
                del self._data[oldest_key]
            self._data[key] = (value, time.monotonic())

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_repo_cache: TTLCache | None = None
_list_cache: TTLCache | None = None
_pr_cache: TTLCache | None = None


def _repo_cache_get() -> TTLCache:
    global _repo_cache
    if _repo_cache is None:
        _repo_cache = TTLCache(CACHE_TTL_REPO)
    return _repo_cache


def _list_cache_get() -> TTLCache:
    global _list_cache
    if _list_cache is None:
        _list_cache = TTLCache(CACHE_TTL_LIST)
    return _list_cache


def _pr_cache_get() -> TTLCache:
    global _pr_cache
    if _pr_cache is None:
        _pr_cache = TTLCache(CACHE_TTL_PR)
    return _pr_cache


def cached_repo(full_name: str, fetcher: Callable[[], T]) -> T:
    """Return cached repo or call fetcher and cache result."""
    c = _repo_cache_get()
    key = f"repo:{full_name}"
    out = c.get(key)
    if out is not None:
        return out
    out = fetcher()
    c.set(key, out)
    return out


def cached_list(cache_key: str, ttl: float, fetcher: Callable[[], T]) -> T:
    """Generic cached list (e.g. list_prs, list_repos)."""
    c = _list_cache_get()
    out = c.get(cache_key)
    if out is not None:
        return out
    out = fetcher()
    c.set(cache_key, out)
    return out


def cached_pr(repo_full_name: str, number: int, fetcher: Callable[[], T]) -> T:
    """Return cached get_pr result or fetch and cache."""
    c = _pr_cache_get()
    key = f"pr:{repo_full_name}:{number}"
    out = c.get(key)
    if out is not None:
        return out
    out = fetcher()
    c.set(key, out)
    return out


def clear_caches() -> None:
    """Clear all caches (e.g. after long-running write operations)."""
    for cache in (_repo_cache, _list_cache, _pr_cache):
        if cache is not None:
            cache.clear()
