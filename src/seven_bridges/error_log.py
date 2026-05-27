"""Error logging: persist per-request error events to JSONL.

Every failed upstream request writes one line to logs/errors.jsonl
with error details and request metadata for debugging and alerting.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ERROR_LOG_PATH = Path(__file__).parent.parent.parent / "logs" / "errors.jsonl"

_MAX_MESSAGE_LEN = 500


def log_error(
    *,
    bridge: str,
    model_alias: str,
    backend_model: str,
    status_code: int,
    error_type: str,
    message: str,
    latency_ms: float | None = None,
    stream: bool = False,
    tool_count: int = 0,
    has_images: bool = False,
    has_video: bool = False,
    client_app: str | None = None,
    session_id: str | None = None,
    **extra: Any,
) -> None:
    """Write a single error event to logs/errors.jsonl.

    Failures are silently ignored so logging never breaks a request.
    """
    try:
        truncated = message
        if len(truncated) > _MAX_MESSAGE_LEN:
            truncated = truncated[:_MAX_MESSAGE_LEN] + "..."

        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": session_id,
            "bridge": bridge,
            "model_alias": model_alias,
            "backend_model": backend_model,
            "status_code": status_code,
            "error_type": error_type,
            "error_message": truncated,
            "stream": stream,
            "latency_ms": latency_ms,
            "tool_count": tool_count,
            "has_images": has_images,
            "has_video": has_video,
            "client_app": client_app,
        }
        entry.update(extra)

        ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass
