"""Rate limiting, admin auth and Calendly webhook signature verification."""
from __future__ import annotations

import hashlib
import hmac
import threading
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

from app.config import get_settings


class RateLimiter:
    """Sliding-window, in-memory limiter. Per process: fine for a single instance."""

    def __init__(self, max_calls: int, window_seconds: int) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    def check(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            cutoff = now - self.window
            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.max_calls:
                return False, int(hits[0] + self.window - now) + 1

            hits.append(now)

            if now - self._last_sweep > 300:  # drop idle keys so memory can't grow forever
                for k in list(self._hits):
                    dq = self._hits[k]
                    while dq and dq[0] <= cutoff:
                        dq.popleft()
                    if not dq:
                        del self._hits[k]
                self._last_sweep = now
            return True, 0


def rate_limit(max_calls: int, window_seconds: int = 60):
    """Build a FastAPI dependency limiting each client IP to max_calls per window."""
    limiter = RateLimiter(max_calls, window_seconds)

    def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        ok, retry_after = limiter.check(ip)
        if not ok:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a minute and try again.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    expected = get_settings().admin_token
    if not expected:
        raise HTTPException(status_code=503, detail="Admin access is not configured.")
    if not x_admin_token or not hmac.compare_digest(
        x_admin_token.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid admin token.")


def verify_calendly_signature(raw_body: bytes, header: str | None) -> None:
    """Validate Calendly's HMAC signature. Skipped entirely if no signing key is configured."""
    key = get_settings().calendly_signing_key
    if not key:
        return
    if not header:
        raise HTTPException(status_code=401, detail="Missing signature.")

    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    t, v1 = parts.get("t"), parts.get("v1")
    if not t or not v1:
        raise HTTPException(status_code=401, detail="Malformed signature.")
    try:
        timestamp = int(t)
    except ValueError:
        raise HTTPException(status_code=401, detail="Malformed signature.")
    if abs(time.time() - timestamp) > 180:
        raise HTTPException(status_code=401, detail="Stale signature.")

    expected = hmac.new(
        key.encode("utf-8"), f"{t}.".encode("utf-8") + raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, v1):
        raise HTTPException(status_code=401, detail="Invalid signature.")