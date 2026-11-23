import logging
import re
import time
import uuid
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings
from app.core.logging import request_id_ctx

REQUEST_ID_HEADER = b"x-request-id"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

logger = logging.getLogger("app.access")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        raw_request_id = headers.get(REQUEST_ID_HEADER, b"").decode("latin-1")
        request_id = (
            raw_request_id
            if REQUEST_ID_PATTERN.fullmatch(raw_request_id)
            else uuid.uuid4().hex
        )

        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        token = request_id_ctx.set(request_id)

        started_at = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message):
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_started = True
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != REQUEST_ID_HEADER
                ]
                headers.append((REQUEST_ID_HEADER, request_id.encode("latin-1")))
                message = {**message, "headers": headers}
                
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            if response_started:
                extra = {
                    "request_id": request_id,
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "user_id": state.get("user_id"),
                }
                if duration_ms >= settings.slow_request_ms:
                    extra["slow"] = True
                    logger.warning("request_completed", extra=extra)
                else:
                    logger.info("request_completed", extra=extra)
            request_id_ctx.reset(token)
