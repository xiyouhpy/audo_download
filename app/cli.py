"""命令行入口：磁力抓取任务（by-date / by-code 二选一）。"""
import argparse
import sys
from dataclasses import replace
from datetime import date

from app.service import run
from app.settings import RunConfig


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="搜索磁力并经 spider API 写入",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  %(prog)s by-date --start-date 2026-04-20 --end-date 2026-04-30
  %(prog)s by-code MIDA-636
  %(prog)s by-code MIDA-636 ABC-123 -v
""",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="同时输出到终端",
    )
    sub = p.add_subparsers(dest="mode", required=True)

    p_date = sub.add_parser(
        "by-date",
        help="按作品发行日从 spider 拉番号并抓取",
    )
    p_date.add_argument("--start-date", required=True, metavar="YYYY-MM-DD")
    p_date.add_argument("--end-date", required=True, metavar="YYYY-MM-DD")

    p_code = sub.add_parser("by-code", help="抓取指定番号")
    p_code.add_argument("codes", nargs="+", metavar="CODE")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = RunConfig()

    if args.mode == "by-date":
        cfg = replace(cfg, start_date=args.start_date, end_date=args.end_date)
        return run(cfg, codes=None, verbose=args.verbose)

    today = date.today().isoformat()
    cfg = replace(cfg, start_date=today, end_date=today)
    return run(cfg, codes=args.codes, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
