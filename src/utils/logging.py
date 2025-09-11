import json
import logging
import re
import sys
from datetime import datetime
from logging import LogRecord
from typing import Optional

from src.config import settings

# PHI patterns to scrub from logs
PHI_PATTERNS = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]"),  # SSN
    (r"\b\d{3}-\d{3}-\d{4}\b", "[PHONE]"),  # Phone
    (r"\(\d{3}\)\s*\d{3}-\d{4}", "[PHONE]"),  # Phone with area code
    (r"\b[A-Z]{2}\d{6,8}\b", "[MRN]"),  # Medical Record Number
    (r"\b\d{10,12}\b", "[ID]"),  # Generic ID numbers
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL]"),  # Email
    (
        r"\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b",
        "[DATE]",
    ),  # Dates
]


class PHIScrubber:
    """Scrub PHI from log messages."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.patterns = [(re.compile(p), r) for p, r in PHI_PATTERNS] if enabled else []

    def scrub(self, text: str) -> str:
        """Remove PHI from text."""
        if not self.enabled or not text:
            return text

        scrubbed = text
        for pattern, replacement in self.patterns:
            scrubbed = pattern.sub(replacement, scrubbed)

        return scrubbed


class JSONFormatter(logging.Formatter):
    """JSON log formatter with PHI scrubbing."""

    def __init__(self, scrubber: Optional[PHIScrubber] = None):
        super().__init__()
        self.scrubber = scrubber or PHIScrubber(enabled=settings.log_scrub_phi)

    def format(self, record: LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self.scrubber.scrub(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            for key, value in record.extra_fields.items():
                if isinstance(value, str):
                    value = self.scrubber.scrub(value)
                log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class StandardFormatter(logging.Formatter):
    """Standard text formatter with PHI scrubbing."""

    def __init__(self, scrubber: Optional[PHIScrubber] = None):
        super().__init__(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.scrubber = scrubber or PHIScrubber(enabled=settings.log_scrub_phi)

    def format(self, record: LogRecord) -> str:
        """Format log record with PHI scrubbing."""
        original_msg = record.msg
        record.msg = self.scrubber.scrub(str(record.msg))
        formatted = super().format(record)
        record.msg = original_msg
        return formatted


class CustomLogger(logging.LoggerAdapter):
    """Custom logger with extra fields support."""

    def process(self, msg, kwargs):
        """Process log message and kwargs."""
        extra = kwargs.get("extra", {})
        extra["extra_fields"] = kwargs.pop("extra_fields", {})
        kwargs["extra"] = extra
        return msg, kwargs

    def log_with_context(self, level: int, msg: str, **context):
        """Log with additional context fields."""
        self.log(level, msg, extra_fields=context)


def configure_logging(
    level: Optional[str] = None, format_type: Optional[str] = None
) -> None:
    """Configure application logging."""
    log_level = getattr(logging, (level or settings.log_level).upper())
    log_format = format_type or settings.log_format

    # Create scrubber
    scrubber = PHIScrubber(enabled=settings.log_scrub_phi)

    # Choose formatter
    if log_format == "json":
        formatter = JSONFormatter(scrubber)
    else:
        formatter = StandardFormatter(scrubber)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set specific log levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> CustomLogger:
    """Get a logger instance with PHI scrubbing."""
    return CustomLogger(logging.getLogger(name), {})


# Initialize logging on module import
configure_logging()
