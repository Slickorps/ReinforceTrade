"""
Utility modules for ReinforceTrade.

Exports:
    logger           — StructuredLogger singleton (JSON + console)
    set_trace_id     — Inject trace ID for current context
    set_request_id   — Inject request ID for current context
    get_trace_id     — Get current trace ID
    get_request_id   — Get current request ID
"""

from .logger import (
    logger,
    set_trace_id,
    get_trace_id,
    set_request_id,
    get_request_id,
    get_log_file_path,
    _StructuredLogger,
)

__all__ = [
    "logger",
    "set_trace_id",
    "get_trace_id",
    "set_request_id",
    "get_request_id",
    "get_log_file_path",
    "_StructuredLogger",
]