import base64
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

_SIZE_RE = re.compile(
    r"([\d.]+)\s*(B|KB|MB|GB|TB|Byte|Bytes)", re.IGNORECASE
)
_UNITS = {"b": 1, "byte": 1, "bytes": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4}


def normalize_code(code: str) -> str:
    return code.replace("-", "").lower()


def code_in_text(code: str, text: str) -> bool:
    return bool(text) and normalize_code(code) in normalize_code(text)


def parse_size(text: str) -> int:
    m = _SIZE_RE.search((text or "").strip())
    if not m:
        return 0
    unit = m.group(2).lower()
    return int(float(m.group(1)) * _UNITS.get(unit, 0))


def magnet_to_thunder(magnet: str) -> str:
    return "thunder://" + base64.b64encode(f"AA{magnet}ZZ".encode()).decode()


@dataclass
class SearchItem:
    group_name: str
    detail_path: str
    total_size: int
    total_size_text: str
    title: str


def parse_search_results(html: str, code: str) -> list[SearchItem]:
    items = []
    for panel in BeautifulSoup(html, "lxml").select("div.panel.search-panel"):
        heading = panel.select_one(".panel-heading h3.panel-title a")
        if not heading or not heading.get("href", "").startswith("/detail/"):
            continue
        group = _group_name(panel)
        if not code_in_text(code, group):
            continue
        files = [
            li.find("span").get_text(" ", strip=True)
            for li in panel.select(".panel-body ul.list-unstyled > li")
            if li.find("span") and li.find("span").get_text(strip=True)
        ]
        if not any(".mp4" in f.lower() for f in files):
            continue
        size_text, size_bytes = _footer_size(panel)
        items.append(
            SearchItem(
                group_name=group,
                detail_path=heading["href"],
                total_size=size_bytes,
                total_size_text=size_text,
                title=heading.get_text(" ", strip=True),
            )
        )
    return items


def _group_name(panel) -> str:
    for li in panel.select(".panel-body ul.list-unstyled > li"):
        span = li.find("span")
        if not span:
            continue
        hl = span.find("span", class_="highlight")
        if hl and len(hl.get_text(strip=True)) <= 30:
            return hl.get_text(strip=True)
    a = panel.select_one(".panel-heading h3.panel-title a")
    if a:
        hl = a.find("span", class_="highlight")
        return hl.get_text(strip=True) if hl else a.get_text(" ", strip=True)
    return ""


def _footer_size(panel) -> tuple[str, int]:
    footer = panel.select_one(".panel-footer.pbc")
    if not footer:
        return "", 0
    m = re.search(
        r"文件大小:\s*([\d.]+\s*(?:B|KB|MB|GB|TB|Byte|Bytes))",
        footer.get_text(" ", strip=True),
        re.I,
    )
    text = m.group(1).strip() if m else ""
    return text, parse_size(text)
