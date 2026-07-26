"""Request protections shared by Nani's API routes."""
from __future__ import annotations

import hmac
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from fastapi import HTTPException, Request, status

from app.config import get_settings


class SlidingWindowRateLimiter:
    """In-memory per-client limiter.

    It intentionally has no external dependency, which keeps a small Render
    deployment simple. Limits are per process; use a shared limiter/store when
    deploying multiple replicas.
    """

    def __init__(self) -> None:
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> Tuple[bool, int]:
        settings = get_settings()
        now = time.monotonic()
        window_start = now - settings.rate_limit_window_seconds
        with self._lock:
            timestamps = self._requests[key]
            while timestamps and timestamps[0] <= window_start:
                timestamps.popleft()
            if len(timestamps) >= settings.rate_limit_requests:
                retry_after = max(1, int(settings.rate_limit_window_seconds - (now - timestamps[0])) + 1)
                return False, retry_after
            timestamps.append(now)
            # Avoid keeping abandoned IP keys forever.
            if len(self._requests) > 5000:
                stale_keys = [name for name, values in self._requests.items() if not values or values[-1] <= window_start]
                for name in stale_keys:
                    self._requests.pop(name, None)
            return True, 0


chat_rate_limiter = SlidingWindowRateLimiter()


def client_identifier(request: Request) -> str:
    """Use Render's first forwarded address when available."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()[:100]
    return request.client.host if request.client else "unknown"


def enforce_chat_rate_limit(request: Request) -> None:
    allowed, retry_after = chat_rate_limiter.check(client_identifier(request))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many messages. Please wait a moment and try again.",
            headers={"Retry-After": str(retry_after)},
        )


def require_admin(request: Request) -> None:
    """Require the dashboard token without ever echoing it in a response."""
    expected = get_settings().admin_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The dashboard is disabled until ADMIN_TOKEN is configured.",
        )
    provided = request.headers.get("x-admin-token", "")
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Dashboard authentication required.")
