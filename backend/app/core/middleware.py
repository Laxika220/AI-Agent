"""Pure-ASGI middleware (safe for streaming/SSE responses)."""

import time
import uuid

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import AuthenticationError
from app.core.logging import get_logger
from app.utils.auth import decode_token

logger = get_logger("http")


class AuthContextMiddleware:
    """Decode a Bearer access token (if any) and inject `request.state.user_id`.

    Invalid or missing tokens are not rejected here; protected routes enforce auth
    through the `get_current_user` dependency, which loads the full user and sets
    `request.state.current_user`.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            state = scope.setdefault("state", {})
            state["user_id"] = None
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode("latin-1")
            scheme, _, token = auth_header.partition(" ")
            if scheme.lower() == "bearer" and token:
                try:
                    state["user_id"] = decode_token(token.strip(), "access").sub
                except AuthenticationError:
                    pass
        await self.app(scope, receive, send)


class RequestLoggingMiddleware:
    """Attach a request id to every log line and log one access line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex[:12]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", [])
                message["headers"].append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            logger.info(
                "request",
                method=scope["method"],
                path=scope["path"],
                status=status_code,
                duration_ms=round((time.perf_counter() - start) * 1000, 1),
            )
