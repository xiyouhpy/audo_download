import logging
import re
import sys
import time
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

from app.parsers import SearchItem, magnet_to_thunder, make_soup, parse_search_results
from app.settings import LAOWANG_URL

logger = logging.getLogger(__name__)
_CHALLENGE = ("Checking your browser", "recaptcha", "Bot Challenge", "网址安全中心")
_MAGNET_PATTERNS = (
    r"magnet:\?xt=[^\s\"'<>]+",
    r"thunder://[A-Za-z0-9+/=]+",
)
_CHROMIUM_ARGS = ["--disable-blink-features=AutomationControlled"]
if sys.platform == "linux":
    _CHROMIUM_ARGS.extend(["--no-sandbox", "--disable-setuid-sandbox"])


class LaowangBrowser:
    def __init__(self, base_url: str = LAOWANG_URL, headless: bool = True):
        self.base_url = base_url.rstrip("/")
        self.headless = headless
        self._pw = self._browser = self._ctx = self._page = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless, args=_CHROMIUM_ARGS
        )
        self._ctx = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
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

    def _ready_search_page(self) -> None:
        logger.info("打开老王并等待搜索页…")
        self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=90000)
        for _ in range(40):
            if self._page.locator('input[name="keyword"]').count():
                return
            if any(m in self._page.content() for m in _CHALLENGE):
                time.sleep(1)
                continue
            time.sleep(1)
        raise RuntimeError("无法进入老王搜索页（无 keyword 输入框）")

    def search(self, code: str, page_num: int = 1, *, _retry: bool = False) -> str:
        self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)
        if not self._page.locator('input[name="keyword"]').count():
            self._ready_search_page()
        time.sleep(1)
        self._page.fill('input[name="keyword"]', code)
        if page_num > 1:
            self._page.evaluate(
                f"() => {{ const p = document.querySelector('input[name=p]');"
                f" if (p) p.value = '{page_num}'; }}"
            )
        self._page.click("button.search-btn")
        try:
            self._page.wait_for_selector("div.panel.search-panel", timeout=60000)
        except Exception:
            try:
                self._page.wait_for_selector("text=为您索检", timeout=60000)
            except Exception:
                self._page.wait_for_load_state("networkidle", timeout=60000)
        time.sleep(1)
        html = self._page.content()
        if (
            not _retry
            and page_num == 1
            and not make_soup(html).select("div.panel.search-panel")
        ):
            logger.warning("%s 搜索无结果块，重新进入搜索页后重试", code)
            self._ready_search_page()
            return self.search(code, page_num, _retry=True)
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
