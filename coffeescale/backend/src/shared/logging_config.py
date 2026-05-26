"""Structured JSON logging for all CoffeeScale Lambdas.

All Lambdas call get_logger(__name__) to get a pre-configured logger that
emits CloudWatch-friendly JSON with mandatory fields.
"""

import json
import logging
import os
import sys


class _JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON for CloudWatch Logs Insights."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "lambda": os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "local"),
            "request_id": os.environ.get("_X_AMZN_TRACE_ID", "local"),
            "message": record.getMessage(),
        }
        # Merge any extra fields passed via LoggerAdapter or extra={}
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "taskName",
            } and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Return a JSON-structured logger scoped to *name*."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, os.environ.get("LOG_LEVEL", level)))
    logger.propagate = False
    return logger
