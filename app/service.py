"""抓取流程：拉番号 → 老王搜索 → 写入 MySQL。"""
import logging
import time

from app.db import MagnetDB
from app.env_check import log_runtime_env
from app.laowang import LaowangBrowser
from app.magnet_link import update_magnet_links_by_code
from app.log_util import setup_logger
from app.settings import SKIP_DOWNLOAD_IF_COUNT_OVER, RunConfig
from app.works import fetch_works

logger = setup_logger("app.service", "log/download.log")


def _process_code(
    db: MagnetDB,
    browser: LaowangBrowser,
    cfg: RunConfig,
    code: str,
    *,
    works_download_cnt: int | None = None,
) -> tuple[int, int]:
    """返回 (写入链接数, 未命中 0/1)。"""
    try:
        links = browser.collect_links(
            code, cfg.min_size_bytes, cfg.max_links_per_code
        )
    except Exception as exc:
        logger.exception("搜索失败: %s", exc)
        update_magnet_links_by_code(
            db,
            code,
            [{"miss_reason": f"error: {exc}"}],
            start_date=cfg.start_date,
            end_date=cfg.end_date,
            works_download_cnt=works_download_cnt,
        )
        return 0, 1

    if not links:
        logger.warning("%s 无符合结果", code)
        update_magnet_links_by_code(
            db,
            code,
            [{"miss_reason": "no_match"}],
            start_date=cfg.start_date,
            end_date=cfg.end_date,
            works_download_cnt=works_download_cnt,
        )
        return 0, 1

    result = update_magnet_links_by_code(
        db,
        code,
        links,
        start_date=cfg.start_date,
        end_date=cfg.end_date,
        works_download_cnt=works_download_cnt,
    )
    n = result.links_inserted
    logger.info(
        "%s 写入 %s 条（抓取 %s 条），spider download_cnt 同步=%s",
        code,
        n,
        len(links),
        "成功" if result.works_api_ok else "失败",
    )
    return n, 0


def run(cfg: RunConfig, codes: list[str] | None = None) -> int:
    log_runtime_env()
    works_by_code = (
        fetch_works(cfg.start_date, cfg.end_date, cfg.works_page_size)
        if not codes
        else {}
    )
    work_codes = codes or list(works_by_code.keys())
    if not codes:
        logger.info("从 API 获取 %s 个番号", len(work_codes))

    m = cfg.mysql
    logger.info(
        "MySQL 目标: %s@%s:%s/%s（每条写入后立即提交）",
        m.user,
        m.host,
        m.port,
        m.database,
    )

    link_count = miss_count = skip_count = 0
    with MagnetDB(cfg.mysql) as db, LaowangBrowser(
        cfg.laowang_url, cfg.headless
    ) as browser:
        for i, code in enumerate(work_codes, 1):
            logger.info("[%s/%s] %s", i, len(work_codes), code)
            existing = db.count_download_links(code)
            if existing > SKIP_DOWNLOAD_IF_COUNT_OVER:
                logger.info(
                    "%s 库内已有 %s 条下载链接（>%s），跳过",
                    code,
                    existing,
                    SKIP_DOWNLOAD_IF_COUNT_OVER,
                )
                skip_count += 1
                continue
            n, miss = _process_code(
                db,
                browser,
                cfg,
                code,
                works_download_cnt=works_by_code.get(code),
            )
            db.commit()
            logger.info("%s 已提交 MySQL", code)
            link_count += n
            miss_count += miss
            time.sleep(cfg.request_delay_sec)

    logger.info(
        "完成：链接 %s 条，未命中 %s 条，跳过 %s 条",
        link_count,
        miss_count,
        skip_count,
    )
    return 0 if link_count else 1
