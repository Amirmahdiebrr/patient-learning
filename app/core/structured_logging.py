"""
app/core/structured_logging.py

A logging.Formatter that emits JSON lines carrying the standard
fields (timestamp, level, logger name, message) plus whatever request
context is currently set in app.core.request_context (request_id,
hospital_id, department_id, patient_id, admin_id). This is the format
consumed by ELK/OpenSearch once shipped there; until then it's just
readable JSON in stdout.

In DEBUG mode we fall back to the original human-readable single-line
format instead, since JSON is harder to eyeball during local
development.
"""

import json
import logging

from app.core.request_context import get_log_context


class JSONRequestFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(get_log_context())

        extra_fields = getattr(record, "extra_fields", None)
        if extra_fields:
            payload.update(extra_fields)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)