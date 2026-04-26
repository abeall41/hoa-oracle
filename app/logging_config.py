"""
Structured JSON logging for HOA Oracle.
Call configure_logging() once at startup in main.py.
Writes to logs/app.log (JSON lines) and stdout.
"""
import logging
import logging.handlers
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            obj["exc"] = traceback.format_exception(*record.exc_info)
        for key in ("query", "community_id", "query_source", "latency_ms", "doc_id", "tool"):
            if hasattr(record, key):
                obj[key] = getattr(record, key)
        return json.dumps(obj)


def configure_logging(log_dir: str = "logs") -> None:
    Path(log_dir).mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Rotating file handler — JSON lines, 10 MB per file, keep 7
    file_handler = logging.handlers.RotatingFileHandler(
        f"{log_dir}/app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(_JsonFormatter())

    # Stdout handler — human-readable for journald / terminal
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
    )

    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    # Quiet noisy third-party loggers
    for noisy in ("httpx", "httpcore", "sentence_transformers", "transformers", "torch"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
