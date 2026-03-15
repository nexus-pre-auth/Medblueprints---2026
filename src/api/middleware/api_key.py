"""
API Key Authentication Middleware
====================================
Lightweight hardcoded API key auth for the architect demo.
Skip full OAuth/JWT for now — one key gets you in.

Set DEMO_API_KEY in .env (or use the default for local testing).
Pass as header:  X-API-Key: your-key
             or: ?api_key=your-key  (for browser URL testing)

Exempt paths: /health, /docs, /openapi.json, /redoc, /
"""
import os
import secrets
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Paths that never require auth
EXEMPT_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/_next",
    "/favicon",
)
EXEMPT_EXACT = {"/"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Simple API key gate.
    Checks X-API-Key header, then ?api_key= query param.
    If REQUIRE_API_KEY=false (default for local dev), all requests pass through.
    """

    def __init__(self, app, require_auth: bool = False, valid_keys: Optional[set] = None):
        super().__init__(app)
        self.require_auth = require_auth
        self.valid_keys: set[str] = valid_keys or set()

    async def dispatch(self, request: Request, call_next):
        if not self.require_auth:
            return await call_next(request)

        path = request.url.path
        if path in EXEMPT_EXACT or any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return await call_next(request)

        key = (
            request.headers.get("X-API-Key")
            or request.query_params.get("api_key")
        )

        if not key or not self._validate(key):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Invalid or missing API key. "
                    "Pass X-API-Key header or ?api_key= query param.",
                    "docs": "/docs",
                },
            )
        return await call_next(request)

    def _validate(self, key: str) -> bool:
        return any(secrets.compare_digest(key, valid) for valid in self.valid_keys)


def load_api_keys() -> set[str]:
    """Load valid API keys from environment."""
    keys = set()

    # Primary demo key
    demo_key = os.environ.get("DEMO_API_KEY", "demo-medblueprints-2026")
    if demo_key:
        keys.add(demo_key)

    # Additional keys (comma-separated for multiple architects)
    extra = os.environ.get("API_KEYS", "")
    for k in extra.split(","):
        k = k.strip()
        if k:
            keys.add(k)

    return keys
