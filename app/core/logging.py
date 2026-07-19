from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configures the root logger once at application startup."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def get_logger(name: str = "app") -> logging.Logger:
    """Returns a standard-library logger. `logging.getLogger(name)` is
    itself idempotent (the same name always returns the same object), so
    this is just a thin, explicit accessor used to construct the one
    logger instance passed into every service/repository/client via DI.
    """
    return logging.getLogger(name)
