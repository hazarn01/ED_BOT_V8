from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to inject standard security headers and sane caching.

    Also enforces UTF-8 charset for text responses when missing.
    """

    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)

        # Security headers
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )

        # Basic CSP for dev (Swagger UI handled elsewhere)
        if not response.headers.get("Content-Security-Policy"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "img-src 'self' data:; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'"
            )

        # Enforce UTF-8 charset for text responses
        content_type = response.headers.get("content-type") or response.headers.get("Content-Type")
        if content_type and content_type.startswith("text/") and "charset=" not in content_type.lower():
            response.headers["Content-Type"] = f"{content_type}; charset=utf-8"

        # Caching rules
        path = request.url.path
        if path.startswith("/static/"):
            # Long cache only for versioned assets
            if "v=" in (request.url.query or ""):
                response.headers.setdefault(
                    "Cache-Control", "public, max-age=31536000, immutable"
                )
            else:
                response.headers.setdefault(
                    "Cache-Control", "public, max-age=300"
                )
        elif path in ("/", "/index.html"):
            # Never cache HTML shell
            response.headers.setdefault("Cache-Control", "no-store")

        return response


def set_secure_cookie(
    response,
    key: str,
    value: str,
    *,
    max_age: int | None = None,
    expires: int | str | None = None,
    domain: str | None = None,
    path: str = "/",
    secure: bool = True,
    httponly: bool = True,
    samesite: str = "Lax",
):
    """Helper to set hardened cookies consistently."""
    response.set_cookie(
        key,
        value,
        max_age=max_age,
        expires=expires,
        domain=domain,
        path=path,
        secure=secure,
        httponly=httponly,
        samesite=samesite,
    )



