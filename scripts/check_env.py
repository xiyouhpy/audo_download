#!/usr/bin/env python3
"""检查本机/VM 运行环境与 Playwright（与 cron 使用同一 python 运行）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.env_check import check_playwright_chromium, log_runtime_env
from app.log_util import setup_logger

logger = setup_logger("app.check_env", "log/check_env.log")


def main() -> int:
    log_runtime_env()
    err = check_playwright_chromium(headless=True)
    if err:
        print(f"FAIL: {err}", file=sys.stderr)
        return 1
    print("OK: Playwright Chromium 可用")
    # 可选：探测老王首页
    try:
        from playwright.sync_api import sync_playwright
        import app.laowang as lw

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True, args=lw._CHROMIUM_ARGS
            )
            ctx = browser.new_context(locale="zh-CN")
            page = ctx.new_page()
            from app.settings import LAOWANG_URL

            page.goto(LAOWANG_URL, wait_until="domcontentloaded", timeout=90000)
            kw = page.locator('input[name="keyword"]').count()
            title = page.title()
            html_len = len(page.content())
            print(f"laowang: title={title!r} html_len={html_len} keyword_inputs={kw}")
            browser.close()
    except Exception as exc:
        print(f"WARN: 老王首页探测失败: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
