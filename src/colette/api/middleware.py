"""API middleware — request-ID injection, rate limiting, graceful degradation."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from colette.config import Settings

# ---------------------------------------------------------------------------
# Request-ID injection
# ---------------------------------------------------------------------------


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Injects a unique ``X-Request-ID`` header into every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# Rate limiting (in-memory token bucket per API key)
# ---------------------------------------------------------------------------


class _Bucket:
    __slots__ = ("last_refill", "tokens")

    def __init__(self, capacity: int) -> None:
        self.tokens: float = float(capacity)
        self.last_refill: float = time.monotonic()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter.

    Uses a token-bucket per API key (or IP if no key).
    Returns 429 with ``Retry-After`` on limit exceeded.
    """

    def __init__(self, app: FastAPI, settings: Settings) -> None:
        super().__init__(app)
        self._limit = settings.api_rate_limit_per_minute
        self._admin_limit = settings.api_admin_rate_limit_per_minute
        self._buckets: dict[str, _Bucket] = defaultdict(lambda: _Bucket(self._limit))

    def _get_key(self, request: Request) -> str:
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            return f"key:{api_key}"
        client = request.client
        return f"ip:{client.host}" if client else "ip:unknown"

    def _refill(self, bucket: _Bucket, capacity: int) -> None:
        now = time.monotonic()
        elapsed = now - bucket.last_refill
        bucket.tokens = min(float(capacity), bucket.tokens + elapsed * (capacity / 60.0))
        bucket.last_refill = now

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip rate limiting for health endpoints.
        if request.url.path in ("/health", "/ready"):
            return await call_next(request)

        key = self._get_key(request)
        capacity = self._admin_limit if key.startswith("key:") else self._limit
        bucket = self._buckets[key]
        self._refill(bucket, capacity)

        if bucket.tokens < 1.0:
            return Response(
                content='{"error": {"code": "rate_limited", "message": "Too many requests"}}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"},
            )
        bucket.tokens -= 1.0
        return await call_next(request)


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


class GracefulDegradationMiddleware(BaseHTTPMiddleware):
    """Catches infrastructure errors and returns 503 instead of 500."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except ConnectionRefusedError:
            return Response(
                content='{"error": {"code": "service_unavailable", '
                '"message": "Backend service unavailable"}}',
                status_code=503,
                media_type="application/json",
                headers={"Retry-After": "30"},
            )
        except OSError as exc:
            if "Connection" in str(exc):
                return Response(
                    content='{"error": {"code": "service_unavailable", '
                    '"message": "Backend connection error"}}',
                    status_code=503,
                    media_type="application/json",
                    headers={"Retry-After": "30"},
                )
            raise
