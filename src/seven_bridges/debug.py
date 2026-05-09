"""Debug middleware: logs every request/response pair to JSONL files."""

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

DEBUG_DIR = Path(__file__).parent.parent.parent / "logs" / "debug"
DEBUG_ENABLED = os.environ.get("BRIDGE_DEBUG", "").lower() in ("1", "true", "yes")


def _ensure_debug_dir() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)


class DebugMiddleware(BaseHTTPMiddleware):
    """Capture request/response bodies and write them to per-session JSONL files."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not DEBUG_ENABLED:
            return await call_next(request)

        _ensure_debug_dir()
        session_id = str(uuid.uuid4())[:8]
        started_at = time.time()

        # Capture request body
        body_bytes = b""
        if request.method in ("POST", "PUT", "PATCH"):
            body_bytes = await request.body()

            # Re-inject so downstream can still read it
            async def receive() -> dict[str, Any]:
                return {"type": "http.request", "body": body_bytes, "more_body": False}

            request = Request(request.scope, receive, request._send)

        req_body: object = None
        try:
            req_body = json.loads(body_bytes) if body_bytes else None
        except json.JSONDecodeError:
            req_body = body_bytes.decode("utf-8", errors="replace") if body_bytes else None

        request_entry = {
            "type": "request",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%f"),
            "session_id": session_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params),
            "headers": dict(request.headers.items()),
            "body": req_body,
        }

        # Write request line
        log_path = DEBUG_DIR / f"{session_id}.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(request_entry, ensure_ascii=False, default=str) + "\n")

        # Call handler
        response = await call_next(request)
        duration_ms = round((time.time() - started_at) * 1000, 2)

        # Capture response body
        resp_body: object = None
        if isinstance(response, StreamingResponse):
            resp_body = "<streaming_response>"
        else:
            resp_body_bytes = b""
            body_iter = getattr(response, "body_iterator", None)
            if body_iter is not None:
                async for chunk in body_iter:
                    resp_body_bytes += chunk
            # Rebuild response so client still gets it
            response = Response(
                content=resp_body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers.items()),
                media_type=response.media_type,
            )
            try:
                resp_body = json.loads(resp_body_bytes) if resp_body_bytes else None
            except json.JSONDecodeError:
                text = resp_body_bytes.decode("utf-8", errors="replace")
                resp_body = text if resp_body_bytes else None

        response_entry = {
            "type": "response",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%f"),
            "session_id": session_id,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "headers": dict(response.headers.items()),
            "body": resp_body,
        }

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(response_entry, ensure_ascii=False, default=str) + "\n")

        return response
