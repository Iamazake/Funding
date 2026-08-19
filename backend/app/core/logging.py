from __future__ import annotations

import logging
from typing import Any
from urllib.parse import unquote_plus

ONEDRIVE_CALLBACK_PATH = "/api/integrations/onedrive/callback"
SENSITIVE_QUERY_MARKERS = (
    "access_token",
    "authorization",
    "client_secret",
    "code",
    "cookie",
    "password",
    "refresh_token",
    "session",
    "state",
    "token",
)


class OAuthCallbackAccessLogFilter(logging.Filter):
    """Remove OAuth queries and redact accidental sensitive query parameters."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple) or len(args) < 3:
            return True
        target = args[2]
        if not isinstance(target, str) or "?" not in target:
            return True
        sanitized: list[Any] = list(args)
        path, query = target.split("?", 1)
        if ONEDRIVE_CALLBACK_PATH in path:
            sanitized[2] = path
        else:
            parts = []
            for item in query.split("&"):
                raw_key, separator, value = item.partition("=")
                key = unquote_plus(raw_key).casefold()
                if any(marker in key for marker in SENSITIVE_QUERY_MARKERS):
                    parts.append(f"{raw_key}=[REDACTED]")
                else:
                    parts.append(f"{raw_key}{separator}{value}")
            sanitized[2] = f"{path}?{'&'.join(parts)}"
        record.args = tuple(sanitized)
        return True


def install_sensitive_access_log_filter() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, OAuthCallbackAccessLogFilter) for item in logger.filters):
        logger.addFilter(OAuthCallbackAccessLogFilter())
