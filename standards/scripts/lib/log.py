"""Logging setup for repo tooling.

One rule, applied everywhere in this repository: **stdout carries the payload,
stderr carries everything a human reads.** An agent invoking one of these
scripts pipes stdout into a JSON parser; a single stray ``print()`` of a
progress message turns valid output into a parse error at the worst possible
moment. So diagnostics go through ``logging``, which is wired to stderr here
and nowhere else.
"""

from __future__ import annotations

import logging
import sys

ROOT_LOGGER_NAME = "crv"

_LEVEL_PREFIX = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARNING: "warning",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
}


class _PlainFormatter(logging.Formatter):
    """``level: message`` with no timestamp.

    Timestamps make CI logs diff noisily and tell a human nothing they cannot
    get from the surrounding job output.
    """

    def format(self, record: logging.LogRecord) -> str:
        prefix = _LEVEL_PREFIX.get(record.levelno, record.levelname.lower())
        message = record.getMessage()
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"
        return f"{prefix}: {message}"


def configure(verbose: bool = False, quiet: bool = False) -> logging.Logger:
    """Attach a single stderr handler to the ``crv`` logger and return it.

    Args:
        verbose: emit DEBUG records.
        quiet: emit only WARNING and above. Ignored when ``verbose`` is set,
            because asking for both is a scripting mistake and the safer
            reading is "show me more".
    """
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING
    else:
        level = logging.INFO
    logger.setLevel(level)
    logger.propagate = False

    for existing in list(logger.handlers):
        logger.removeHandler(existing)

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(_PlainFormatter())
    handler.setLevel(level)
    logger.addHandler(handler)
    return logger


def get_logger(suffix: str) -> logging.Logger:
    """Return the child logger ``crv.<suffix>``."""
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{suffix}")
