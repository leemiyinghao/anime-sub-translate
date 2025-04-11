import logging
from typing import Literal

from xtermcolor import colorize

logging.basicConfig(
    level=logging.CRITICAL,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("Anime-Sub-Translate")
logger.propagate = False
logger.handlers.clear()
handler = logging.StreamHandler()
handler.formatter = logging.Formatter(
    f"{colorize('%(asctime)s - %(levelname)s - ', ansi=243)}%(message)s"
)
logger.addHandler(handler)

LOG_LEVEL = Literal[
    "debug",
    "info",
    "warning",
    "error",
    "critical",
]


def set_log_level(level: LOG_LEVEL) -> None:
    """
    Set the log level for the logger.
    """
    match level:
        case "debug":
            logger.setLevel(logging.DEBUG)
        case "info":
            logger.setLevel(logging.INFO)
        case "warning":
            logger.setLevel(logging.WARNING)
        case "error":
            logger.setLevel(logging.ERROR)
        case "critical":
            logger.setLevel(logging.CRITICAL)


__all__ = ["logger", "set_log_level", "LOG_LEVEL"]
