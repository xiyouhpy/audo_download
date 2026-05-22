"""抓取流程：拉番号 → 老王搜索 → 经 spider API 写入 magnet_link。"""
import logging
import time

import httpx

from app.laowang import LaowangBrowser
from app.settings import PROJECT_ROOT, SKIP_DOWNLOAD_IF_COUNT_OVER, RunConfig
from app.spider_client import (
    count_download_links,
    fetch_works,
    update_magnet_links_by_code,
)

logger = logging.getLogger(__name__)


def _setup_app_logging(
    log_file: str = "log/download.log",
    *,
    verbose: bool = False,
) -> None:
    """配置 app 包统一日志；默认仅写文件，--verbose 时同时输出到终端。"""
    app_logger = logging.getLogger("app")
    if app_logger.handlers:
        return
    (PROJECT_ROOT / "log").mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
    handlers: list[logging.Handler] = [
        logging.FileHandler(PROJECT_ROOT / log_file, encoding="utf-8"),
    ]
    if verbose:
        handlers.append(logging.StreamHandler())
    for handler in handlers:
        handler.setFormatter(fmt)
        app_logger.addHandler(handler)


def _report_miss(
    code: str,
    reason: str,
    cfg: RunConfig,
    client: httpx.Client,
    *,
    works_download_cnt: int | None = None,
) -> None:
    update_magnet_links_by_code(
        code,
        [{"miss_reason": reason}],
        start_date=cfg.start_date,
        end_date=cfg.end_date,
        works_download_cnt=works_download_cnt,
        client=client,
    )


def _process_code(
    browser: LaowangBrowser,
    cfg: RunConfig,
    code: str,
    client: httpx.Client,
    *,
    works_download_cnt: int | None = None,
) -> tuple[int, int]:
    """返回 (写入链接数, 未命中 0/1)。"""
    try:
        links = browser.collect_links(
            code,
            cfg.min_size_bytes,
            cfg.max_links_per_code,
            cfg.max_search_pages,
        )
    except Exception as exc:
        logger.exception("搜索失败: %s", exc)
        _report_miss(
            code, f"error: {exc}", cfg, client, works_download_cnt=works_download_cnt
        )
        return 0, 1

    if not links:
        logger.warning("%s 无符合结果", code)
        _report_miss(code, "no_match", cfg, client, works_download_cnt=works_download_cnt)
        return 0, 1

    result = update_magnet_links_by_code(
        code,
        links,
        start_date=cfg.start_date,
        end_date=cfg.end_date,
        works_download_cnt=works_download_cnt,
        client=client,
    )
    n = result.links_inserted
    logger.info(
        "%s 写入 %s 条（抓取 %s 条），库内链接 %s 条，download_cnt 同步=%s",
        code,
        n,
        len(links),
        result.download_cnt,
        "成功" if result.works_api_ok else "失败",
    )
    return n, 0


def run(cfg: RunConfig, codes: list[str] | None = None, *, verbose: bool = False) -> int:
    _setup_app_logging(verbose=verbose)
    with httpx.Client(timeout=60.0) as client:
        works_by_code = (
            fetch_works(
                cfg.start_date, cfg.end_date, cfg.works_page_size, client=client
            )
            if not codes
            else {}
        )
        work_codes = codes or list(works_by_code.keys())
        if not codes:
            logger.info("从 spider API 获取 %s 个番号", len(work_codes))

        logger.info("数据写入 spider API，日期 %s ~ %s", cfg.start_date, cfg.end_date)

        link_count = miss_count = skip_count = 0
        with LaowangBrowser(cfg.laowang_url, cfg.headless) as browser:
            for i, code in enumerate(work_codes, 1):
                logger.info("[%s/%s] %s", i, len(work_codes), code)
                existing = count_download_links(code, client=client)
                if existing > SKIP_DOWNLOAD_IF_COUNT_OVER:
                    logger.info(
                        "%s 已有 %s 条链接（>%s），跳过",
                        code,
                        existing,
                        SKIP_DOWNLOAD_IF_COUNT_OVER,
                    )
                    skip_count += 1
                    continue
                n, miss = _process_code(
                    browser,
                    cfg,
                    code,
                    client,
                    works_download_cnt=works_by_code.get(code),
                )
                if not miss:
                    logger.info("%s 已提交 spider", code)
                link_count += n
                miss_count += miss
                time.sleep(cfg.request_delay_sec)

    logger.info(
        "完成：链接 %s 条，未命中 %s 条，跳过 %s 条",
        link_count,
        miss_count,
        skip_count,
    )
    return 0
