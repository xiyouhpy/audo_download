#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from app.service import run  # noqa: E402
from app.settings import (  # noqa: E402
    DEFAULT_PAGE_SIZE,
    LAOWANG_BASE_URL,
    MIN_SIZE_GB,
    MySQLConfig,
    RunConfig,
    load_dotenv,
)


def build_mysql_config(args: argparse.Namespace) -> MySQLConfig:
    cfg = MySQLConfig.from_env()
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


def main():
    load_dotenv()
    p = argparse.ArgumentParser(description="搜索磁力并写入 MySQL")
    p.add_argument("--start-date", required=True)
    p.add_argument("--end-date", required=True)
    p.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    p.add_argument("--min-size-gb", type=float, default=MIN_SIZE_GB)
    p.add_argument("--max-links", type=int, default=20)
    p.add_argument("--base-url", default=LAOWANG_BASE_URL)
    p.add_argument("--delay", type=float, default=2.0)
    p.add_argument("--headed", action="store_true")
    p.add_argument("--codes", nargs="*")
    p.add_argument("--mysql-host")
    p.add_argument("--mysql-port", type=int)
    p.add_argument("--mysql-user")
    p.add_argument("--mysql-password")
    p.add_argument("--mysql-database")
    args = p.parse_args()

    cfg = RunConfig(
        start_date=args.start_date,
        end_date=args.end_date,
        mysql=build_mysql_config(args),
        works_page_size=args.page_size,
        laowang_base_url=args.base_url,
        min_size_gb=args.min_size_gb,
        min_size_bytes=int(args.min_size_gb * 1024**3),
        max_links_per_code=args.max_links,
        request_delay_sec=args.delay,
        headless=not args.headed,
    )
    sys.exit(run(cfg, args.codes or None))


if __name__ == "__main__":
    main()
