"""Simple in-process sliding-window rate limiter for login attempts.

NOTE: In-process only. A multi-process / multi-instance production deployment
needs a shared store (e.g. Redis). Documented as a Phase 10 follow-up.
"""
from __future__ import annotations

import threading
import time

from app.config import get_settings

_settings = get_settings()
_lock = threading.Lock()
_attempts: dict[str, list[float]] = {}


def is_rate_limited(key: str) -> bool:
    now = time.monotonic()
    window = _settings.login_window_seconds
    with _lock:
        hits = [t for t in _attempts.get(key, []) if now - t < window]
        _attempts[key] = hits
        return len(hits) >= _settings.login_max_attempts


def record_attempt(key: str) -> None:
    now = time.monotonic()
    with _lock:
        _attempts.setdefault(key, []).append(now)


def is_limited(key: str, max_attempts: int, window_seconds: int) -> bool:
    """Generic sliding-window check for non-login actions (e.g. AI generation)."""
    now = time.monotonic()
    with _lock:
        hits = [t for t in _attempts.get(key, []) if now - t < window_seconds]
        _attempts[key] = hits
        if len(hits) >= max_attempts:
            return True
        hits.append(now)
        return False


def reset(key: str) -> None:
    with _lock:
        _attempts.pop(key, None)


def clear_all() -> None:
    with _lock:
        _attempts.clear()
