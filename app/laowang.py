import logging
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from app.parsers import SearchItem, magnet_to_thunder, parse_search_results
from app.settings import LAOWANG_BASE_URL

logger = logging.getLogger(__name__)
_CHALLENGE = ("Checking your browser", "recaptcha", "Bot Challenge")


class LaowangBrowser:
    def __init__(self, base_url: str = LAOWANG_BASE_URL, headless: bool = True):
        self.base_url = base_url.rstrip("/")
        self.headless = headless
        self._pw = self._browser = self._ctx = self._page = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        self._ctx = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        self._page = self._ctx.new_page()
        self._pass_challenge()
        return self

    def __exit__(self, *args):
        if self._ctx:
            self._ctx.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def _pass_challenge(self):
        logger.info("通过首页反爬…")
        self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=90000)
        for _ in range(25):
            if not any(m in self._page.content() for m in _CHALLENGE):
                return
            time.sleep(1)

    def search(self, code: str, page_num: int = 1) -> str:
        self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(1)
        self._page.fill('input[name="keyword"]', code)
        if page_num > 1:
            self._page.evaluate(
                f"() => {{ const p = document.querySelector('input[name=p]');"
                f" if (p) p.value = '{page_num}'; }}"
            )
        self._page.click("button.search-btn")
        try:
            self._page.wait_for_selector("text=为您索检", timeout=90000)
        except Exception:
            self._page.wait_for_load_state("networkidle", timeout=90000)
        time.sleep(1)
        return self._page.content()

    def collect_links(
        self, code: str, min_bytes: int, max_links: int = 20
    ) -> list[dict]:
        html = self.search(code)
        soup = BeautifulSoup(html, "lxml")
        extra_pages = set()
        for a in soup.select("nav.pagination a.spbtn, nav.pagination a.spbtna"):
            m = re.search(r"searchWithPath\((\d+)\)", a.get("onclick", ""))
            if m:
                extra_pages.add(int(m.group(1)))
        for p in sorted(extra_pages):
            if 1 < p <= 5:
                html += self.search(code, p)

        hits = sorted(
            [x for x in parse_search_results(html, code) if x.total_size >= min_bytes],
            key=lambda x: x.total_size,
        )[:max_links]

        out = []
        for item in hits:
            magnet = self._fetch_magnet(item)
            if not magnet:
                continue
            out.append(
                {
                    "code": code,
                    "group_name": item.group_name,
                    "title": item.title,
                    "total_size_text": item.total_size_text,
                    "magnet": magnet,
                    "thunder": magnet_to_thunder(magnet),
                }
            )
            time.sleep(0.5)
        return out

    def _fetch_magnet(self, item: SearchItem) -> str | None:
        page = self._ctx.new_page()
        try:
            page.goto(
                urljoin(self.base_url, item.detail_path),
                wait_until="domcontentloaded",
                timeout=90000,
                referer=self._page.url,
            )
            for _ in range(20):
                html = page.content()
                if m := re.findall(r"magnet:\?xt=[^\s\"'<>]+", html):
                    return m[0]
                time.sleep(1)
        finally:
            page.close()
        logger.warning("未获取 magnet: %s", item.detail_path)
        return None
