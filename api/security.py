"""Anonymous browser ownership and small public-demo request limits.

The cookie is an unguessable bearer token. Only its SHA-256 digest is persisted
with a run; clearing browser cookies intentionally loses access to old runs.
"""

import hashlib
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse

COOKIE_NAME = "framekind_session"
TOKEN_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_guard = threading.Lock()
_requests: dict[str, deque] = defaultdict(deque)


class RequestBodyLimit:
    """Bound request bodies before multipart parsing, including chunked uploads."""

    def __init__(self, app, upload_max_bytes: int):
        self.app = app
        self.upload_max_bytes = upload_max_bytes

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope.get("method") not in {"POST", "PUT", "PATCH"}
            or not scope.get("path", "").startswith("/api/")
        ):
            await self.app(scope, receive, send)
            return
        maximum = self.upload_max_bytes if scope["path"].endswith("/assets") else 64 * 1024
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > maximum:
                response = JSONResponse({"detail": "Upload is too large"}, status_code=413)
                await response(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        supplied = False

        async def replay():
            nonlocal supplied
            if not supplied:
                supplied = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def browser_identity(request: Request) -> tuple[str, str, bool]:
    token = request.cookies.get(COOKIE_NAME, "")
    fresh = not TOKEN_PATTERN.fullmatch(token)
    if fresh:
        token = secrets.token_hex(32)
    return token, hashlib.sha256(token.encode()).hexdigest(), fresh


def verify_origin(request: Request) -> None:
    """Browsers may mutate their own runs only from this application's origin."""
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).netloc != request.headers.get("host"):
        raise HTTPException(status_code=403, detail="Cross-origin changes are not allowed")


def limit_request(key: str, maximum: int, window_seconds: int = 3600) -> None:
    now = time.monotonic()
    with _guard:
        # Remove idle identities so the limiter itself cannot grow indefinitely.
        for old_key in list(_requests):
            if not _requests[old_key] or _requests[old_key][-1] <= now - window_seconds:
                del _requests[old_key]
        events = _requests[key]
        while events and events[0] <= now - window_seconds:
            events.popleft()
        if len(events) >= maximum:
            raise HTTPException(
                status_code=429,
                detail="This demo's hourly limit was reached. Please try again later.",
                headers={"Retry-After": str(window_seconds)},
            )
        events.append(now)


def reset_limits() -> None:
    with _guard:
        _requests.clear()
