"""
OilTrace — Structured logging and run manifests.

Uses stdlib logging with JSON formatting. No external deps.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


class _JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = str(record.exc_info[1])
        return json.dumps(payload)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Return a structured JSON logger.

    Args:
        name: Logger name (typically __name__).
        level: Logging level.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JSONFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


@dataclass
class RunManifest:
    """
    Captures metadata about a processing run for auditability.

    Serialisable to JSON for storage alongside outputs.
    """

    run_id: str
    service: str
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    completed_at: Optional[str] = None
    parameters: dict = field(default_factory=dict)
    status: str = "started"
    error: Optional[str] = None

    def complete(self, status: str = "completed") -> None:
        self.completed_at = datetime.utcnow().isoformat() + "Z"
        self.status = status

    def fail(self, error: str) -> None:
        self.completed_at = datetime.utcnow().isoformat() + "Z"
        self.status = "failed"
        self.error = error

    def to_dict(self) -> dict:
        return asdict(self)
