"""抓取流程：拉番号 → 老王搜索 → 写入 MySQL。"""
import logging
import time

from app.db import MagnetDB
from app.laowang import LaowangBrowser
from app.log_util import setup_logger
from app.settings import RunConfig
from app.works import fetch_codes

logger = setup_logger("auto_download", "log/download.log")


def _process_code(db: MagnetDB, browser: LaowangBrowser, cfg: RunConfig, code: str) -> tuple[int, int]:
    """返回 (写入链接数, 未命中 0/1)。"""
    try:
        links = browser.collect_links(
            code, cfg.min_size_bytes, cfg.max_links_per_code
        )
    except Exception as exc:
        logger.exception("搜索失败: %s", exc)
        db.save_miss(cfg.start_date, cfg.end_date, code, f"error: {exc}")
        return 0, 1

    if not links:
        logger.warning("%s 无符合结果", code)
        db.save_miss(cfg.start_date, cfg.end_date, code, "no_match")
        return 0, 1

    n = db.save_links(cfg.start_date, cfg.end_date, links)
    logger.info("%s 写入 %s 条（抓取 %s 条）", code, n, len(links))
    return n, 0


def run(cfg: RunConfig, codes: list[str] | None = None) -> int:
    work_codes = codes or fetch_codes(
        cfg.start_date, cfg.end_date, cfg.works_page_size, cfg.works_api_base
    )
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

    link_count = miss_count = 0
    with MagnetDB(cfg.mysql) as db, LaowangBrowser(
        cfg.laowang_base_url, cfg.headless
    ) as browser:
        for i, code in enumerate(work_codes, 1):
            logger.info("[%s/%s] %s", i, len(work_codes), code)
            n, miss = _process_code(db, browser, cfg, code)
            db.commit()
            logger.info("%s 已提交 MySQL", code)
            link_count += n
            miss_count += miss
            time.sleep(cfg.request_delay_sec)

    logger.info("完成：链接 %s 条，未命中 %s 条", link_count, miss_count)
    return 0 if link_count else 1
