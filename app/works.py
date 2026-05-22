"""作品（works）相关：通过 spider HTTP 接口拉番号、更新 download_cnt。"""
from __future__ import annotations

import logging

import httpx

from app.settings import SPIDER_WORK_DOWNLOAD_CNT_URL, SPIDER_WORKS_URL

logger = logging.getLogger(__name__)


def fetch_codes(
    start_date: str,
    end_date: str,
    page_size: int = 100,
) -> list[str]:
    codes = []
    page = 1
    with httpx.Client(timeout=30.0) as client:
        while True:
            resp = client.get(
                SPIDER_WORKS_URL,
                params={
                    "page": page,
                    "page_size": page_size,
                    "start_date": start_date,
                    "end_date": end_date,
                    "order_by": "release_date",
                    "order": "asc",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            codes.extend(w["code"] for w in data.get("data") or [] if w.get("code"))
            total = data.get("total_pages") or 1
            logger.info("作品 API %s/%s 页", page, total)
            if page >= total:
                break
            page += 1
    return codes


def update_works_download_cnt(code: str, download_cnt: int) -> None:
    """调用 spider 接口更新作品的 download_cnt（实际写入 magnet_link 的链接条数）。"""
    code = code.strip()
    if not code:
        raise ValueError("code 不能为空")
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            SPIDER_WORK_DOWNLOAD_CNT_URL,
            json={"code": code, "download_cnt": download_cnt},
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
    logger.debug("%s download_cnt=%s 已提交 spider", code, download_cnt)
