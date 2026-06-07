"""
Structured logging module for ReinforceTrade.

Features:
    - JSON-format logging (logstash/ELK compatible)
    - Log level routing: DEBUG → console, INFO+ → file (JSON) + console
    - Automatic request trace ID injection via contextvars
    - Module-level logger factory
    - Sensitive data redaction (API keys, secrets)

Usage:
    from utils import logger
    logger.info("Trade executed", trade_id="abc123", pnl=150.0)

    # Module-level logger
    log = logger.bind(module="backtest")
    log.debug("Processing bar 42")
"""

import json
import os
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger as _base_logger
from config.settings import settings

# ──────────────────────────────────────────────────────────────────────
# Context variables (per-request / per-task injection)
# ──────────────────────────────────────────────────────────────────────
_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_request_id: ContextVar[str] = ContextVar("request_id", default="")

# ──────────────────────────────────────────────────────────────────────
# Sink configuration constants
# ──────────────────────────────────────────────────────────────────────
LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE_JSON = LOG_DIR / "reinforcetrade.json"
LOG_FILE_TEXT = LOG_DIR / "reinforcetrade.log"

# Fields to redact from log output
SENSITIVE_KEYS = frozenset({
    "api_key", "api_secret", "secret", "password", "token",
    "access_token", "refresh_token", "private_key",
})


# ──────────────────────────────────────────────────────────────────────
# Custom formatters
# ──────────────────────────────────────────────────────────────────────

def _redact_sensitive(record: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep copy of record with sensitive values masked."""
    result = dict(record)
    extra = dict(result.get("extra", {}))
    for key in list(extra.keys()):
        if key.lower() in SENSITIVE_KEYS and extra[key]:
            val = str(extra[key])
            extra[key] = val[:4] + "****" if len(val) > 8 else "****"
    result["extra"] = extra
    return result


def _json_serialize(record) -> str:
    """Serialize a Loguru record as a JSON line (logstash-compatible)."""
    subset = _redact_sensitive(record)

    # Build structured payload
    payload: Dict[str, Any] = {
        "@timestamp": datetime.fromtimestamp(
            record["time"].timestamp(), tz=timezone.utc
        ).isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "message": record["message"],
        "module": record.get("extra", {}).pop("module", record["name"]),
        "function": record["function"],
        "line": record["line"],
    }

    # Inject trace / request IDs
    trace_id = _trace_id.get()
    request_id = _request_id.get()
    if trace_id:
        payload["trace_id"] = trace_id
    if request_id:
        payload["request_id"] = request_id

    # Attach extra structured fields
    extra = record.get("extra", {})
    if extra:
        payload["extra"] = extra

    # Include exception info if present
    if record.get("exception"):
        payload["exception"] = {
            "type": record["exception"].type.__name__,
            "value": str(record["exception"].value),
            "traceback": "".join(
                record["exception"].format_traceback() or []
            ),
        }

    return json.dumps(payload, default=str) + "\n"


def _console_format(record) -> str:
    """Colorised console format string."""
    # Level-colour mapping
    level_colors = {
        "TRACE": "white",
        "DEBUG": "cyan",
        "INFO": "green",
        "SUCCESS": "bold green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold red",
    }
    color = level_colors.get(record["level"].name, "white")
    trace = ""
    tid = _trace_id.get()
    rid = _request_id.get()
    if tid:
        trace = f" <dim>[{tid[:8]}]{'</dim>' if True else ''}"
    if rid:
        trace += f" <dim>[{rid[:8]}]{'</dim>' if True else ''}"

    # Use Loguru's built-in markup
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        f"<level><{color}>" + "{level:<8}</" + color + "></level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
        f"{trace}"
        " | <level>{message}</level>"
        "{exception}\n"
    )


# ──────────────────────────────────────────────────────────────────────
# Sink configuration
# ──────────────────────────────────────────────────────────────────────

def _is_serializable(value: Any) -> bool:
    """Check if value is JSON-serializable."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_serializable(v) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _is_serializable(v) for k, v in value.items())
    return False


class _StructuredLogger:
    """
    Wrapper around Loguru that supports structured keyword arguments.

    Usage:
        log = logger.bind(module="backtest")
        log.info("Processing completed", bars=500, duration_sec=12.3)
    """

    def __init__(self, bound: Optional[Dict[str, Any]] = None):
        self._bound = bound or {}

    def bind(self, **kwargs) -> "_StructuredLogger":
        """Return a new logger with extra fields bound."""
        merged = {**self._bound, **kwargs}
        return _StructuredLogger(merged)

    def _log(self, level: str, message: str, **kwargs):
        """Emit a log record with structured extra fields."""
        extra = {**self._bound, **kwargs}
        # Filter out non-serializable values with a warning
        cleaned = {}
        for k, v in extra.items():
            if _is_serializable(v):
                cleaned[k] = v
            else:
                cleaned[k] = str(v)
        _base_logger.opt(depth=2).log(level, message, **cleaned)

    def debug(self, message: str, **kwargs):
        self._log("DEBUG", message, **kwargs)

    def info(self, message: str, **kwargs):
        self._log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log("ERROR", message, **kwargs)

    def critical(self, message: str, **kwargs):
        self._log("CRITICAL", message, **kwargs)

    def success(self, message: str, **kwargs):
        self._log("SUCCESS", message, **kwargs)

    def exception(self, message: str, **kwargs):
        """Log an exception with traceback."""
        _base_logger.opt(depth=2, exception=True).error(message, **kwargs)


# ──────────────────────────────────────────────────────────────────────
# Configure Loguru sinks
# ──────────────────────────────────────────────────────────────────────

_base_logger.remove()  # Remove default handler

# Sink 1: File — JSON (ELK / logstash compatible)
# Rotates daily, retains 30 days
_base_logger.add(
    str(LOG_FILE_JSON),
    format=_json_serialize,
    level=settings.log_level,
    rotation="1 day",
    retention="30 days",
    compression="gz",
    serialize=False,
    enqueue=True,       # thread-safe
    backtrace=True,
    diagnose=False,
)

# Sink 2: File — Plain text (human readable fallback)
_base_logger.add(
    str(LOG_FILE_TEXT),
    format=_console_format,
    level=settings.log_level,
    rotation="1 day",
    retention="7 days",
    enqueue=True,
    backtrace=True,
    diagnose=False,
)

# Sink 3: Console — DEBUG+ (colorised, stderr)
_base_logger.add(
    sys.stderr,
    format=_console_format,
    level="DEBUG",
    colorize=True,
    enqueue=True,
    backtrace=False,
    diagnose=False,
)

# Silence noisy third-party loggers
_base_logger.disable("httpx")
_base_logger.disable("urllib3")


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

# Re-export as module-level singleton
logger: _StructuredLogger = _StructuredLogger()


def set_trace_id(trace_id: Optional[str] = None) -> str:
    """
    Set (or auto-generate) a trace ID for the current context.

    Returns the trace ID.
    """
    tid = trace_id or uuid.uuid4().hex
    _trace_id.set(tid)
    return tid


def get_trace_id() -> str:
    """Return the current trace ID, or empty string if not set."""
    return _trace_id.get()


def set_request_id(request_id: Optional[str] = None) -> str:
    """
    Set (or auto-generate) a request ID for the current request context.

    Returns the request ID.
    """
    rid = request_id or uuid.uuid4().hex
    _request_id.set(rid)
    return rid


def get_request_id() -> str:
    """Return the current request ID, or empty string if not set."""
    return _request_id.get()


def get_log_file_path() -> Path:
    """Return the current JSON log file path."""
    return LOG_FILE_JSON


__all__ = [
    "logger",
    "set_trace_id",
    "get_trace_id",
    "set_request_id",
    "get_request_id",
    "get_log_file_path",
    "_StructuredLogger",
]