"""命令行入口：磁力抓取任务。"""
import argparse
import sys

from app.service import run
from app.settings import (
    DEFAULT_PAGE_SIZE,
    LAOWANG_BASE_URL,
    MAX_LINKS_PER_CODE,
    MIN_SIZE_GB,
    REQUEST_DELAY_SEC,
    MySQLConfig,
    RunConfig,
    load_dotenv,
)


def _apply_mysql_overrides(cfg: MySQLConfig, args: argparse.Namespace) -> MySQLConfig:
    if args.mysql_host:
        cfg.host = args.mysql_host
    if args.mysql_port:
        cfg.port = args.mysql_port
    if args.mysql_user:
        cfg.user = args.mysql_user
    if args.mysql_password:
        cfg.password = args.mysql_password
    if args.mysql_database:
        cfg.database = args.mysql_database
    cfg.validate()
    return cfg


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="搜索磁力并写入 MySQL")
    p.add_argument("--start-date", required=True)
    p.add_argument("--end-date", required=True)
    p.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    p.add_argument("--min-size-gb", type=float, default=MIN_SIZE_GB)
    p.add_argument("--max-links", type=int, default=MAX_LINKS_PER_CODE)
    p.add_argument("--base-url", default=LAOWANG_BASE_URL)
    p.add_argument("--delay", type=float, default=REQUEST_DELAY_SEC)
    p.add_argument("--headed", action="store_true")
    p.add_argument("--codes", nargs="*")
    p.add_argument("--mysql-host")
    p.add_argument("--mysql-port", type=int)
    p.add_argument("--mysql-user")
    p.add_argument("--mysql-password")
    p.add_argument("--mysql-database")
    return p


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    cfg = RunConfig(
        start_date=args.start_date,
        end_date=args.end_date,
        mysql=_apply_mysql_overrides(MySQLConfig.from_env(), args),
        works_page_size=args.page_size,
        laowang_base_url=args.base_url,
        min_size_gb=args.min_size_gb,
        max_links_per_code=args.max_links,
        request_delay_sec=args.delay,
        headless=not args.headed,
    )
    return run(cfg, args.codes or None)


if __name__ == "__main__":
    sys.exit(main())
