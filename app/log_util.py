import logging
from pathlib import Path

from app.settings import PROJECT_ROOT


def setup_logger(name: str, log_file: str) -> logging.Logger:
    """配置 app 包统一日志，子模块（app.laowang 等）会向上传播到 app。"""
    app_logger = logging.getLogger("app")
    if not app_logger.handlers:
        (PROJECT_ROOT / "log").mkdir(parents=True, exist_ok=True)
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
        )
        app_logger.setLevel(logging.INFO)
        app_logger.propagate = False
        for handler in (
            logging.StreamHandler(),
            logging.FileHandler(PROJECT_ROOT / log_file, encoding="utf-8"),
        ):
            handler.setFormatter(fmt)
            app_logger.addHandler(handler)
    return logging.getLogger(name)
