"""
Structured logging configuration with correlation IDs
"""
import logging
import uuid
import sys
import json
from datetime import datetime
from typing import Optional


class JSONFormatter(logging.Formatter):
    """Format log records as JSON"""

    def format(self, record: logging.LogRecord) -> str:
        """Convert log record to JSON string"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Add correlation ID if available
        if hasattr(record, 'correlation_id'):
            log_data['correlation_id'] = record.correlation_id

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    use_json: bool = False
) -> logging.Logger:
    """
    Configure application logging

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for log output
        use_json: Whether to use JSON formatting

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("iam_dynamic")
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = JSONFormatter() if use_json else logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


class CorrelationLogger:
    """
    Logger with correlation ID tracking

    Wraps a standard logger and adds correlation IDs to all log records
    for tracing requests through the system.
    """

    def __init__(self, logger: logging.Logger):
        """
        Initialize correlation logger

        Args:
            logger: Base logger to wrap
        """
        self.logger = logger
        self.correlation_id = str(uuid.uuid4())

    def _log_with_context(
        self,
        level: int,
        msg: str,
        *args,
        **kwargs
    ):
        """Log with correlation ID in context"""
        extra = kwargs.pop('extra', {})
        extra['correlation_id'] = self.correlation_id
        self.logger.log(level, msg, *args, extra=extra, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Log info message with correlation ID"""
        self._log_with_context(logging.INFO, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Log error message with correlation ID"""
        self._log_with_context(logging.ERROR, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning message with correlation ID"""
        self._log_with_context(logging.WARNING, msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        """Log debug message with correlation ID"""
        self._log_with_context(logging.DEBUG, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """Log critical message with correlation ID"""
        self._log_with_context(logging.CRITICAL, msg, *args, **kwargs)


def get_logger(name: str = "iam_dynamic") -> logging.Logger:
    """
    Get a logger instance

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
