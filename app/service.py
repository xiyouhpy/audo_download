"""主流程：拉番号 → 搜索 → 写入 MySQL。"""
import logging
import time

from app.db import MagnetDB
from app.laowang import LaowangBrowser
from app.settings import PROJECT_ROOT, RunConfig
from app.works import fetch_codes

logger = logging.getLogger("auto_download")


def _setup_log():
    if logger.handlers:
        return
    (PROJECT_ROOT / "log").mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    logger.setLevel(logging.INFO)
    for h in (
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "log/download.log", encoding="utf-8"),
    ):
        h.setFormatter(fmt)
        logger.addHandler(h)


def run(cfg: RunConfig, codes: list[str] | None = None) -> int:
    _setup_log()
    work_codes = codes or fetch_codes(
        cfg.start_date, cfg.end_date, cfg.works_page_size, cfg.works_api_base
    )
    if not codes:
        logger.info("从 API 获取 %s 个番号", len(work_codes))

    link_count = 0
    miss_count = 0

    with MagnetDB(cfg.mysql) as db:
        with LaowangBrowser(cfg.laowang_base_url, cfg.headless) as browser:
            for i, code in enumerate(work_codes, 1):
                logger.info("[%s/%s] %s", i, len(work_codes), code)
                try:
                    links = browser.collect_links(
                        code, cfg.min_size_bytes, cfg.max_links_per_code
                    )
                except Exception as exc:
                    logger.exception("搜索失败: %s", exc)
                    db.save_miss(cfg.start_date, cfg.end_date, code, f"error: {exc}")
                    miss_count += 1
                    time.sleep(cfg.request_delay_sec)
                    continue

                if not links:
                    logger.warning("%s 无符合结果", code)
                    db.save_miss(cfg.start_date, cfg.end_date, code, "no_match")
                    miss_count += 1
                else:
                    logger.info("%s 找到 %s 条", code, len(links))
                    db.save_links(cfg.start_date, cfg.end_date, links)
                    link_count += len(links)

                time.sleep(cfg.request_delay_sec)

    logger.info("MySQL 已写入：链接 %s 条，未命中 %s 条", link_count, miss_count)
    return 0 if link_count else 1
