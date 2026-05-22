"""运行环境与 Playwright 依赖检查（便于 VM 排查）。"""
from __future__ import annotations

import importlib.util
import logging
import platform
import sys

logger = logging.getLogger(__name__)
_logged_env = False


def _pkg_version(distribution: str, import_name: str | None = None) -> str:
    try:
        from importlib.metadata import version

        return version(distribution)
    except Exception:
        pass
    try:
        mod = __import__(import_name or distribution)
        return getattr(mod, "__version__", "?")
    except Exception as exc:
        return f"未安装 ({exc})"


def log_runtime_env() -> None:
    """启动时打印 Python、系统、关键包版本（全局只打一次）。"""
    global _logged_env
    if _logged_env:
        return
    _logged_env = True

    logger.info("Python: %s", sys.executable)
    logger.info("版本: %s", sys.version.replace("\n", " "))
    logger.info(
        "系统: %s %s (%s)",
        platform.system(),
        platform.release(),
        platform.machine(),
    )
    has_lxml = importlib.util.find_spec("lxml") is not None
    logger.info(
        "依赖: playwright=%s beautifulsoup4=%s lxml=%s pymysql=%s",
        _pkg_version("playwright"),
        _pkg_version("beautifulsoup4", "bs4"),
        "已安装" if has_lxml else "未安装",
        _pkg_version("pymysql"),
    )
    if not has_lxml:
        logger.warning(
            "lxml 未安装，HTML 解析将退化为 html.parser；建议: %s -m pip install lxml",
            sys.executable,
        )


def check_playwright_chromium(headless: bool = True) -> str | None:
    """
    尝试启动 Chromium 并访问 about:blank。
    成功返回 None，失败返回错误说明。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return f"未安装 playwright: {exc}"

    import app.laowang as lw

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=headless, args=lw._CHROMIUM_ARGS
            )
            page = browser.new_page()
            page.goto("about:blank", timeout=15000)
            browser.close()
    except Exception as exc:
        err = str(exc)
        if "Executable doesn't exist" in err or "BrowserType.launch" in err:
            return (
                "Chromium 未安装或不匹配当前 Python。"
                f"请对同一解释器执行: {sys.executable} -m playwright install chromium"
            )
        return f"Chromium 启动失败: {exc}"
    return None


def log_playwright_check(headless: bool = True) -> None:
    err = check_playwright_chromium(headless=headless)
    if err:
        logger.error("Playwright 检查失败: %s", err)
    else:
        logger.info("Playwright Chromium 检查通过")
