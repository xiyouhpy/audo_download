import logging
from pathlib import Path

from app.settings import PROJECT_ROOT


def setup_logger(name: str, log_file: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    (PROJECT_ROOT / "log").mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    logger.setLevel(logging.INFO)
    for handler in (
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / log_file, encoding="utf-8"),
    ):
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger
