import logging
import random
import re
import time
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

from app.parsers import (
    SearchItem,
    magnet_to_thunder,
    make_soup,
    parse_search_results,
    thunder_to_magnet,
)
from app.settings import LAOWANG_URL, SEARCH_PAGE_MIN_MATCH_RATIO

logger = logging.getLogger(__name__)
_CHALLENGE = ("Checking your browser", "recaptcha", "Bot Challenge", "网址安全中心")
_MAGNET_PATTERNS = (
    r"magnet:\?xt=[^\s\"'<>]+",
    r"thunder://[A-Za-z0-9+/=]+",
)
_NAV_TIMEOUT_MS = 15_000
_CHALLENGE_POLL_S = 1.0
_CHALLENGE_MAX_ATTEMPTS = 5
_MAGNET_POLL_S = 0.5
_MAGNET_MAX_ATTEMPTS = 3
_USER_AGENTS = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) "
    "Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
    "Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
)


def _random_user_agent() -> str:
    return random.choice(_USER_AGENTS)


class LaowangBrowser:
    def __init__(self, base_url: str = LAOWANG_URL, headless: bool = True):
        self.base_url = base_url.rstrip("/")
        self.headless = headless
        self._pw = self._browser = self._ctx = self._page = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        self._ctx = self._browser.new_context(
            user_agent=_random_user_agent(),
            locale="zh-CN",
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

    def _apply_random_user_agent(self, page) -> None:
        page.set_extra_http_headers({"User-Agent": _random_user_agent()})

    def _ready_search_page(self) -> None:
        """打开首页，等到出现搜索框（必要时等待反爬页过去）。"""
        logger.info("打开老王搜索页…")
        self._apply_random_user_agent(self._page)
        self._page.goto(
            self.base_url,
            wait_until="domcontentloaded",
            timeout=_NAV_TIMEOUT_MS,
        )
        for _ in range(_CHALLENGE_MAX_ATTEMPTS):
            if self._page.locator('input[name="keyword"]').count():
                return
            if any(m in self._page.content() for m in _CHALLENGE):
                time.sleep(_CHALLENGE_POLL_S)
                continue
            time.sleep(_CHALLENGE_POLL_S)
        raise RuntimeError("无法进入老王搜索页（无 keyword 输入框）")

    def _page_numbers_from_html(self, html: str) -> list[int]:
        """从 HTML 中解析搜索分页（含 script 里的 searchWithPath）。"""
        pages: set[int] = {1}
        for m in re.finditer(r"searchWithPath\((\d+)\)", html):
            pages.add(int(m.group(1)))
        for a in make_soup(html).select("nav.pagination a"):
            href = a.get("href") or ""
            for m in re.finditer(r"[?&]p=(\d+)", href, re.I):
                pages.add(int(m.group(1)))
            text = (a.get_text() or "").strip()
            if text.isdigit():
                pages.add(int(text))
        return sorted(pages)

    def search(self, code: str, page_num: int = 1) -> str:
        on_search = self._page.locator('input[name="keyword"]').count() > 0
        if page_num == 1 or not on_search:
            self._apply_random_user_agent(self._page)
            self._page.goto(
                self.base_url,
                wait_until="domcontentloaded",
                timeout=_NAV_TIMEOUT_MS,
            )
            if not self._page.locator('input[name="keyword"]').count():
                self._ready_search_page()

        self._page.fill('input[name="keyword"]', code)
        if page_num > 1:
            self._page.evaluate(
                f"() => {{ const p = document.querySelector('input[name=p]');"
                f" if (p) p.value = '{page_num}'; }}"
            )
        self._page.click("button.search-btn")
        try:
            self._page.wait_for_selector(
                "div.panel.search-panel",
                timeout=_NAV_TIMEOUT_MS,
            )
        except Exception:
            self._page.wait_for_selector(
                "text=为您索检",
                timeout=_NAV_TIMEOUT_MS,
            )
        return self._page.content()

    def collect_links(
        self,
        code: str,
        min_bytes: int,
        max_links: int = 20,
        max_search_pages: int = 5,
        min_match_ratio: float = SEARCH_PAGE_MIN_MATCH_RATIO,
    ) -> list[dict]:
        parsed: list[SearchItem] = []
        seen_paths: set[str] = set()

        for page_num in range(1, max_search_pages + 1):
            page_html = self.search(code, page_num)
            raw, page_items = parse_search_results(page_html, code)
            logger.info(
                "%s 第 %s 页 panel=%s 符合=%s",
                code,
                page_num,
                raw,
                len(page_items),
            )

            for item in page_items:
                if item.detail_path in seen_paths:
                    continue
                seen_paths.add(item.detail_path)
                parsed.append(item)

            if raw == 0:
                logger.info("%s 第 %s 页无结果，停止翻页", code, page_num)
                break
            if len(page_items) / raw < min_match_ratio:
                logger.info(
                    "%s 第 %s 页符合率 %.0f%% < %.0f%%，停止翻页",
                    code,
                    page_num,
                    len(page_items) / raw * 100,
                    min_match_ratio * 100,
                )
                break
            if page_num == 1:
                last_available = max(
                    self._page_numbers_from_html(page_html), default=1
                )
                if page_num >= min(last_available, max_search_pages):
                    break

        logger.info("%s 解析 %s 条（已翻 %s 页内）", code, len(parsed), page_num)
        eligible = [x for x in parsed if x.total_size >= min_bytes]
        hits = sorted(eligible, key=lambda x: x.total_size)[:max_links]
        logger.info(
            "%s 体积>=%sGB 共 %s 条，将抓取 magnet 最多 %s 条",
            code,
            min_bytes / (1024**3),
            len(eligible),
            max_links,
        )

        out = []
        for item in hits:
            magnet = self._fetch_magnet(item)
            if not magnet:
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
            time.sleep(0.2)
        return out

    def _extract_magnet(self, html: str) -> str | None:
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
            self._apply_random_user_agent(page)
            page.goto(
                urljoin(self.base_url, item.detail_path),
                wait_until="domcontentloaded",
                timeout=_NAV_TIMEOUT_MS,
                referer=self._page.url,
            )
            for _ in range(_MAGNET_MAX_ATTEMPTS):
                magnet = self._extract_magnet(page.content())
                if magnet:
                    return magnet
                time.sleep(_MAGNET_POLL_S)
        finally:
            page.close()
        logger.warning("未获取 magnet: %s", item.detail_path)
        return None
