import json
import logging
import os
import sys
import time
import uuid
from typing import Any, Dict, Optional


class JsonFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs as JSON.
    Includes timestamp, run_id, level, event, and extra fields.
    """

    def __init__(self, run_id: str) -> None:
        super().__init__()
        self.run_id = run_id

    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "run_id": self.run_id,
            "level": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
        }

        # Merge in structured fields if provided
        if hasattr(record, "fields") and isinstance(record.fields, dict):
            log_record.update(record.fields)

        return json.dumps(log_record, ensure_ascii=False)


# Create a global logger instance
RUN_ID = os.getenv("DQF_RUN_ID", str(uuid.uuid4()))

_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(JsonFormatter(RUN_ID))

logger = logging.getLogger("dqf")
logger.setLevel(os.getenv("DQF_LOG_LEVEL", "INFO").upper())
logger.handlers = [_handler]
logger.propagate = False


def log(event: str, *, level: str = "INFO", **fields: Any) -> None:
    """
    Emit a structured JSON log with given event and fields.
    Example:
        log("check.result", table="APIS_INFO", check="row_count", status="PASS")
    """
    logger.log(
        getattr(logging, level.upper(), logging.INFO),
        event,
        extra={"event": event, "fields": fields},
    )


class ContextLogger:
    """
    Helper to attach constant context (e.g., table/check) to all log calls.
    Example:
        cl = ContextLogger(table="APIS_INFO", check="row_count")
        cl.log("check.start")
        cl.log("check.result", status="PASS", row_count=1000)
    """

    def __init__(self, **context: Any) -> None:
        self.context = context

    def bind(self, **extra: Any) -> "ContextLogger":
        ctx = dict(self.context)
        ctx.update(extra)
        return ContextLogger(**ctx)

    def log(self, event: str, *, level: str = "INFO", **fields: Any) -> None:
        merged = dict(self.context)
        merged.update(fields)
        log(event, level=level, **merged)
