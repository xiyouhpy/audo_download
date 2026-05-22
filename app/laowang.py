import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urljoin

from playwright.sync_api import sync_playwright

from app.env_check import log_playwright_check
from app.parsers import SearchItem, magnet_to_thunder, make_soup, parse_search_results
from app.settings import LAOWANG_URL, PROJECT_ROOT

logger = logging.getLogger(__name__)
_CHALLENGE = (
    "Checking your browser",
    "recaptcha",
    "Bot Challenge",
    "网址安全中心",
    "cf-browser-verification",
    "Just a moment",
    "Access denied",
)
_DEBUG_DIR = PROJECT_ROOT / "log" / "laowang_debug"
_MAGNET_PATTERNS = (
    r"magnet:\?xt=[^\s\"'<>]+",
    r"thunder://[A-Za-z0-9+/=]+",
)
_CHROMIUM_ARGS = ["--disable-blink-features=AutomationControlled"]
if sys.platform == "linux":
    _CHROMIUM_ARGS.extend(["--no-sandbox", "--disable-setuid-sandbox"])


def _default_user_agent() -> str:
    if sys.platform == "linux":
        return (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    return (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )


def _page_signals(html: str) -> dict[str, bool | int]:
    low = html.lower()
    return {
        "html_len": len(html),
        "keyword_input": "name=\"keyword\"" in low or "name='keyword'" in low,
        "search_panel": "search-panel" in low,
        "为您索检": "为您索检" in html,
        "challenge": any(m.lower() in low for m in _CHALLENGE),
    }


def _save_debug_html(code: str, stage: str, html: str) -> Path:
    _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w.-]+", "_", code)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _DEBUG_DIR / f"{safe}_{stage}_{ts}.html"
    path.write_text(html, encoding="utf-8")
    return path


def _has_search_panels(html: str) -> bool:
    return bool(make_soup(html).select("div.panel.search-panel"))


class LaowangBrowser:
    def __init__(self, base_url: str = LAOWANG_URL, headless: bool = True):
        self.base_url = base_url.rstrip("/")
        self.headless = headless
        self._pw = self._browser = self._ctx = self._page = None

    def __enter__(self):
        log_playwright_check(headless=self.headless)
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless, args=_CHROMIUM_ARGS
        )
        ua = _default_user_agent()
        logger.info("Playwright headless=%s UA=%s…", self.headless, ua[:48])
        self._ctx = self._browser.new_context(
            user_agent=ua,
            locale="zh-CN",
            viewport={"width": 1280, "height": 720},
        )
        self._page = self._ctx.new_page()
        self._ready_search_page()
        return self

    def __exit__(self, *args):
        if self._ctx:
            self._ctx.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def _safe_page_html(self) -> str | None:
        """页面跳转过程中 content() 会失败，短暂等待后重试。"""
        for _ in range(30):
            try:
                return self._page.content()
            except Exception as exc:
                msg = str(exc).lower()
                if "navigating" in msg or "changing the content" in msg:
                    try:
                        self._page.wait_for_load_state(
                            "domcontentloaded", timeout=5000
                        )
                    except Exception:
                        pass
                    time.sleep(0.5)
                    continue
                logger.debug("读取页面 HTML 失败: %s", exc)
                time.sleep(1)
        return None

    def _log_page_state(self, code: str, stage: str, *, save_html: bool = False) -> None:
        try:
            url = self._page.url
            title = self._page.title()
            html = self._safe_page_html()
        except Exception as exc:
            logger.warning("%s [%s] 无法读取页面: %s", code, stage, exc)
            return
        if not html:
            logger.warning("%s [%s] 页面 HTML 为空", code, stage)
            return
        sig = _page_signals(html)
        markers = [m for m in _CHALLENGE if m.lower() in html.lower()]
        logger.warning(
            "%s [%s] url=%s title=%r signals=%s challenge=%s",
            code,
            stage,
            url,
            title,
            sig,
            markers or "无",
        )
        if save_html:
            path = _save_debug_html(code, stage, html)
            logger.warning("%s [%s] 已保存页面 HTML: %s", code, stage, path)

    def _ready_search_page(self) -> None:
        logger.info("打开老王并等待搜索页…")
        self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=90000)
        for i in range(40):
            if self._page.locator('input[name="keyword"]').count():
                logger.info("搜索页就绪（等待 %s 秒）", i)
                return
            html = self._safe_page_html()
            if html and any(m in html for m in _CHALLENGE):
                time.sleep(1)
                continue
            time.sleep(1)
        self._log_page_state("", "ready_search_failed", save_html=True)
        raise RuntimeError("无法进入老王搜索页（无 keyword 输入框）")

    def _click_search(self) -> str:
        for sel in (
            "button.search-btn",
            "button[type='submit']",
            ".search-btn",
            "form button",
        ):
            loc = self._page.locator(sel)
            if loc.count():
                logger.info("点击搜索 selector=%s", sel)
                loc.first.click(timeout=10000)
                return sel
        logger.info("未找到搜索按钮，改用 Enter 提交")
        self._page.press('input[name="keyword"]', "Enter")
        return "Enter"

    def _wait_search_results(self, code: str, timeout_sec: int = 90) -> bool:
        start = time.time()
        last_log = 0.0
        while time.time() - start < timeout_sec:
            html = self._safe_page_html()
            if not html:
                time.sleep(1)
                continue
            panels = make_soup(html).select("div.panel.search-panel")
            if panels:
                logger.info(
                    "%s 搜索出结果 search-panel=%s (%.0fs)",
                    code,
                    len(panels),
                    time.time() - start,
                )
                return True
            elapsed = time.time() - start
            if elapsed - last_log >= 15:
                sig = _page_signals(html)
                try:
                    url = self._page.url
                except Exception:
                    url = "?"
                logger.info(
                    "%s 等待搜索结果 %.0fs… url=%s signals=%s",
                    code,
                    elapsed,
                    url,
                    sig,
                )
                last_log = elapsed
            time.sleep(2)
        logger.warning("%s 等待 search-panel 超时 %.0fs", code, timeout_sec)
        return False

    def _search_url(self, code: str, page_num: int = 1) -> str:
        url = f"{self.base_url}/search?keyword={quote(code)}"
        if page_num > 1:
            url += f"&p={page_num}"
        return url

    def _search_via_direct_url(self, code: str, page_num: int) -> str | None:
        url = self._search_url(code, page_num)
        logger.info("%s 直连搜索 page=%s url=%s", code, page_num, url)
        self._page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=90000,
            referer=f"{self.base_url}/",
        )
        self._wait_search_results(code, timeout_sec=30)
        html = self._safe_page_html()
        if html and _has_search_panels(html):
            logger.info("%s 直连搜索成功 search-panel 已出现", code)
            return html
        if html:
            self._log_page_state(code, f"direct_empty_p{page_num}", save_html=True)
        return None

    def _search_via_form(self, code: str, page_num: int) -> str | None:
        if not self._page.locator('input[name="keyword"]').count():
            self._ready_search_page()
        time.sleep(1)
        self._page.fill('input[name="keyword"]', code)
        if page_num > 1:
            self._page.evaluate(
                f"() => {{ const p = document.querySelector('input[name=p]');"
                f" if (p) p.value = '{page_num}'; }}"
            )
        logger.info("%s 表单搜索 page=%s", code, page_num)
        self._click_search()
        try:
            self._page.wait_for_load_state("domcontentloaded", timeout=90000)
        except Exception as exc:
            logger.info("%s 等待 domcontentloaded: %s", code, exc)
        self._wait_search_results(code, timeout_sec=90)
        html = self._safe_page_html()
        if html and _has_search_panels(html):
            logger.info("%s 表单搜索成功 search-panel 已出现", code)
            return html
        if html:
            self._log_page_state(code, f"form_empty_p{page_num}", save_html=True)
        return None

    def search(self, code: str, page_num: int = 1) -> str:
        """表单提交优先（本地可靠）；无结果时再直连 /search?keyword=（VM 回退）。"""
        if page_num == 1 and not self._page.locator('input[name="keyword"]').count():
            self._ready_search_page()
        html = self._search_via_form(code, page_num)
        if html:
            return html
        logger.warning("%s 表单无结果，改直连搜索 page=%s", code, page_num)
        html = self._search_via_direct_url(code, page_num)
        if html:
            return html
        html = self._safe_page_html() or ""
        if not _has_search_panels(html):
            logger.warning(
                "%s 表单与直连均无 search-panel（可能 VM IP 被拦，见 log/laowang_debug/）",
                code,
            )
        return html

    def collect_links(
        self, code: str, min_bytes: int, max_links: int = 20
    ) -> list[dict]:
        html = self.search(code)
        soup = make_soup(html)
        extra_pages = set()
        for a in soup.select("nav.pagination a.spbtn, nav.pagination a.spbtna"):
            m = re.search(r"searchWithPath\((\d+)\)", a.get("onclick", ""))
            if m:
                extra_pages.add(int(m.group(1)))
        for p in sorted(extra_pages):
            if 1 < p <= 5:
                html += self.search(code, p)

        panel_count = len(
            make_soup(html).select("div.panel.search-panel")
        )
        parsed = parse_search_results(html, code)
        logger.info(
            "%s 页面 search-panel=%s，解析 %s 条",
            code,
            panel_count,
            len(parsed),
        )
        if panel_count and not parsed:
            logger.warning("%s 有结果块但解析为 0（番号/格式过滤）", code)
        if not panel_count:
            logger.warning("%s 搜索页无 search-panel（可能未进入老王搜索页）", code)
        hits = sorted(
            [x for x in parsed if x.total_size >= min_bytes],
            key=lambda x: x.total_size,
        )[:max_links]
        if parsed and not hits:
            sizes = ", ".join(x.total_size_text or "?" for x in parsed[:5])
            logger.warning(
                "%s 有 %s 条结果但均小于体积阈值（%s bytes），示例: %s",
                code,
                len(parsed),
                min_bytes,
                sizes,
            )

        out = []
        magnet_fail = 0
        for item in hits:
            magnet = self._fetch_magnet(item)
            if not magnet:
                magnet_fail += 1
                continue
            out.append(
                {
                    "code": code,
                    "thunder_url": magnet_to_thunder(magnet),
                    "group_name": item.group_name,
                    "title": item.title,
                    "total_size_text": item.total_size_text,
                }
            )
            time.sleep(0.5)
        if hits and not out:
            logger.warning(
                "%s %s 条符合体积的结果均未解析到 magnet", code, len(hits)
            )
        elif magnet_fail:
            logger.info("%s magnet 失败 %s/%s 条", code, magnet_fail, len(hits))
        return out

    def _extract_magnet(self, html: str) -> str | None:
        from app.parsers import thunder_to_magnet

        for pattern in _MAGNET_PATTERNS:
            if m := re.findall(pattern, html, flags=re.I):
                url = m[0]
                if url.lower().startswith("magnet:"):
                    return url
                if url.lower().startswith("thunder://"):
                    return thunder_to_magnet(url)
        return None

    def _fetch_magnet(self, item: SearchItem) -> str | None:
        page = self._ctx.new_page()
        try:
            page.goto(
                urljoin(self.base_url, item.detail_path),
                wait_until="domcontentloaded",
                timeout=90000,
                referer=self._page.url,
            )
            try:
                page.wait_for_selector(
                    "a[href^='magnet:'], a[href^='thunder://']",
                    timeout=20000,
                )
            except Exception:
                pass
            for _ in range(15):
                magnet = self._extract_magnet(page.content())
                if magnet:
                    return magnet
                time.sleep(1)
        finally:
            page.close()
        logger.warning("未获取 magnet: %s %s", item.detail_path, item.title)
        return None
