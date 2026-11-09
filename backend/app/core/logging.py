"""Structured logging configuration (structlog)."""

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    """Configure structlog + stdlib logging.

    JSON output is meant for production (log aggregation); the console renderer
    is meant for local development.
    """
    log_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if json_logs:
        processors += [structlog.processors.dict_tracebacks, structlog.processors.JSONRenderer()]
    else:
        processors += [structlog.dev.ConsoleRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Route third-party stdlib logs (uvicorn, pymongo, httpx...) to stdout too.
    logging.basicConfig(level=log_level, stream=sys.stdout, format="%(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpcore", "chromadb.telemetry", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
