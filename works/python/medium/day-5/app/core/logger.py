import logging
import os
import sys

from colorlog import ColoredFormatter

def get_logger(name: str | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers: return logger

    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if os.getenv("LOG_FORMAT") == "json":
        formatter = logging.Formatter(
            fmt='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    else:
        formatter = ColoredFormatter(
            fmt="%(log_color)s[%(asctime)s] %(levelname)-8s %(name)s:%(reset)s %(message)s",
            datefmt="%H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
