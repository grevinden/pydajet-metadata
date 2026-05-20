from __future__ import annotations

import logging
import os
import sys
from typing import Optional

_LOGGER_NAME = "pydajet_metadata.build"


def configure_logging(level: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    resolved_level = (level or os.environ.get("PYDAJET_BUILD_LOG_LEVEL", "INFO")).upper()
    logger.setLevel(getattr(logging, resolved_level, logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    base_logger = configure_logging()
    if not name:
        return base_logger
    return base_logger.getChild(name)
