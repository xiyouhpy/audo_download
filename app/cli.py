"""命令行入口：磁力抓取任务。"""
import argparse
import sys

from app.service import run
from app.settings import (
    DEFAULT_PAGE_SIZE,
    LAOWANG_URL,
    MAX_LINKS_PER_CODE,
    MAX_SEARCH_PAGES,
    MIN_SIZE_GB,
    REQUEST_DELAY_SEC,
    RunConfig,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="搜索磁力并经 spider API 写入")
    p.add_argument("--start-date", required=True)
    p.add_argument("--end-date", required=True)
    p.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    p.add_argument("--min-size-gb", type=float, default=MIN_SIZE_GB)
    p.add_argument("--max-links", type=int, default=MAX_LINKS_PER_CODE)
    p.add_argument("--max-search-pages", type=int, default=MAX_SEARCH_PAGES)
    p.add_argument("--base-url", default=LAOWANG_URL)
    p.add_argument("--delay", type=float, default=REQUEST_DELAY_SEC)
    p.add_argument("--headed", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true", help="同时输出到终端")
    p.add_argument("--codes", nargs="*")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = RunConfig(
        start_date=args.start_date,
        end_date=args.end_date,
        works_page_size=args.page_size,
        laowang_url=args.base_url,
        min_size_gb=args.min_size_gb,
        max_links_per_code=args.max_links,
        max_search_pages=args.max_search_pages,
        request_delay_sec=args.delay,
        headless=not args.headed,
    )
    return run(cfg, args.codes or None, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
