import logging
import sys
import datetime
from logging.handlers import RotatingFileHandler

from pythonjsonlogger import jsonlogger
from opentelemetry import trace


class ContextFilter(logging.Filter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        record.service = self.service_name

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.is_valid:
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        else:
            record.trace_id = ""
            record.span_id = ""

        return True


def setup_logger(service_name: str) -> logging.Logger:
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    formatter = jsonlogger.JsonFormatter(
        fmt="%(timestamp)s %(service)s %(levelname)s %(message)s %(trace_id)s %(span_id)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    context_filter = ContextFilter(service_name)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(context_filter)

    file_handler = RotatingFileHandler(
        f"/logs/{service_name}.log",
        maxBytes=50 * 1024 * 1024,
        backupCount=3,
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)

    return logger
