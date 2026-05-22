#!/usr/bin/env python3
"""调试老王搜索 IPZ-844：打印各阶段命中数量。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.parsers import parse_search_results, parse_size
from app.settings import MIN_SIZE_GB, gb_to_bytes
from app.laowang import LaowangBrowser


def main() -> int:
    code = "IPZ-844"
    min_bytes = gb_to_bytes(MIN_SIZE_GB)
    print(f"code={code} min_size={MIN_SIZE_GB}GB ({min_bytes} bytes)")

    with LaowangBrowser(headless=True) as browser:
        html = browser.search(code)
        print(f"search html length: {len(html)}")
        if "为您索检" not in html and "search-panel" not in html:
            print("WARN: 页面可能不是搜索结果（含反爬/跳转页）")
            print(html[:800])

        items = parse_search_results(html, code)
        print(f"parse_search_results: {len(items)} 条")
        for it in items[:5]:
            print(
                f"  - {it.group_name!r} size={it.total_size_text} "
                f"bytes={it.total_size} path={it.detail_path}"
            )

        hits = [x for x in items if x.total_size >= min_bytes]
        print(f"size >= {MIN_SIZE_GB}GB: {len(hits)} 条")

        if not hits and items:
            print("可能被体积过滤；全部结果体积：")
            for it in items[:10]:
                print(f"  {it.total_size_text} -> {it.total_size}")

        links = browser.collect_links(code, min_bytes, max_links=3)
        print(f"collect_links 最终: {len(links)} 条")
        for L in links:
            print(f"  thunder={L.get('thunder_url', '')[:60]}...")

    return 0 if links else 1


if __name__ == "__main__":
    raise SystemExit(main())
