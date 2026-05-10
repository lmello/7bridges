"""Debug middleware: logs every request/response pair to JSONL files."""

import json
import os
import time
import traceback
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

DEBUG_DIR = Path(__file__).parent.parent.parent / "logs" / "debug"
DEBUG_ENABLED = os.environ.get("BRIDGE_DEBUG", "").lower() in ("1", "true", "yes")
_MAX_DEBUG_FILES = 100


def _ensure_debug_dir() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def _cleanup_old_logs(max_files: int = _MAX_DEBUG_FILES) -> None:
    """Keep only the N most recent debug log files to prevent unbounded growth."""
    try:
        files = sorted(DEBUG_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old_file in files[max_files:]:
            old_file.unlink(missing_ok=True)
    except OSError:
        pass  # Best-effort cleanup


class DebugMiddleware(BaseHTTPMiddleware):
    """Capture request/response bodies and write them to per-session JSONL files.

    Every request gets a unique session_id. Both request and response are
    written to the same JSONL file so you can follow a single conversation
    end-to-end.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not DEBUG_ENABLED:
            return await call_next(request)

        _ensure_debug_dir()
        _cleanup_old_logs()
        session_id = str(uuid.uuid4())[:8]
        started_at = time.time()

        # Capture request body for all methods that might have one
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
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": session_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params) if request.query_params else None,
            "headers": dict(request.headers.items()),
            "body": req_body,
        }

        # Write request line immediately so logs exist even if handler crashes
        log_path = DEBUG_DIR / f"{session_id}.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(request_entry, ensure_ascii=False, default=str) + "\n")

        # Call handler
        response = await call_next(request)
        handler_done_at = time.time()

        # Capture response body
        resp_body: object = None
        if self._is_streaming_response(response):
            resp_body, response = await self._capture_streaming_response(
                response, log_path, started_at, handler_done_at
            )
        else:
            resp_body, response = await self._capture_response_body(response)

        finished_at = time.time()
        response_entry = {
            "type": "response",
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": session_id,
            "status_code": response.status_code,
            "duration_ms": round((finished_at - started_at) * 1000, 2),
            "headers": dict(response.headers.items()),
            "body": resp_body,
        }

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(response_entry, ensure_ascii=False, default=str) + "\n")

        return response

    def _is_streaming_response(self, response: Response) -> bool:
        """Check if a response is streaming.

        Starlette's BaseHTTPMiddleware wraps StreamingResponse in an internal
        _StreamingResponse class, so isinstance() alone is not reliable.
        """
        if isinstance(response, StreamingResponse):
            return True
        body_iter = getattr(response, "body_iterator", None)
        return body_iter is not None and hasattr(body_iter, "__aiter__")

    async def _capture_streaming_response(
        self,
        response: Response,
        log_path: Path,
        started_at: float,
        handler_done_at: float,
    ) -> tuple[str, Response]:
        """Consume a StreamingResponse, log the full text, and rebuild it.

        Returns (captured_body_text, rebuilt_response).
        """
        stream_start_at = time.time()
        chunks: list[bytes] = []
        body_iter = getattr(response, "body_iterator", None)

        try:
            if body_iter is not None:
                async for raw in body_iter:
                    if isinstance(raw, bytes):
                        chunks.append(raw)
                    elif isinstance(raw, str):
                        chunks.append(raw.encode("utf-8"))
                    else:
                        # memoryview or other buffer protocol
                        chunks.append(bytes(raw))
        except Exception as exc:
            # Log the error so it's not silent, then return a graceful 500
            error_entry = {
                "type": "stream_error",
                "timestamp": datetime.now(UTC).isoformat(),
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(error_entry, ensure_ascii=False, default=str) + "\n")

            return (
                f"<stream_error: {exc}>",
                Response(
                    content=json.dumps(
                        {
                            "type": "error",
                            "error": {
                                "type": "internal_error",
                                "message": "Stream capture failed",
                            },
                        }
                    ),
                    status_code=500,
                    media_type="application/json",
                ),
            )

        stream_end_at = time.time()
        body_bytes = b"".join(chunks)

        # Also write an intermediate "stream_body" entry with the raw SSE text
        # so you can inspect the full response without scrolling through deltas
        stream_entry = {
            "type": "stream_body",
            "timestamp": datetime.now(UTC).isoformat(),
            "content_length": len(body_bytes),
            "handler_latency_ms": round((handler_done_at - started_at) * 1000, 2),
            "stream_duration_ms": round((stream_end_at - stream_start_at) * 1000, 2),
            "text": body_bytes.decode("utf-8", errors="replace"),
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(stream_entry, ensure_ascii=False, default=str) + "\n")

        # Rebuild the response so the client still receives the stream
        async def _replay() -> AsyncIterator[bytes]:
            for chunk in chunks:
                yield chunk

        rebuilt = StreamingResponse(
            content=_replay(),
            status_code=response.status_code,
            headers=dict(response.headers.items()),
            media_type=response.media_type,
        )
        return f"<streaming_response: {len(body_bytes)} bytes>", rebuilt

    async def _capture_response_body(self, response: Response) -> tuple[object, Response]:
        """Capture the body of a non-streaming response.

        Returns (parsed_body, rebuilt_response).
        """
        chunks: list[bytes] = []
        body_iter = getattr(response, "body_iterator", None)
        if body_iter is not None:
            async for chunk in body_iter:
                chunks.append(chunk)

        body_bytes = b"".join(chunks)

        # Rebuild response so client still gets it
        rebuilt = Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers.items()),
            media_type=response.media_type,
        )

        if not body_bytes:
            return None, rebuilt

        try:
            return json.loads(body_bytes), rebuilt
        except json.JSONDecodeError:
            return body_bytes.decode("utf-8", errors="replace"), rebuilt
