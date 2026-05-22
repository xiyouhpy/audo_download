"""作品（works）相关：通过 spider HTTP 接口拉番号、更新 download_cnt。"""
from __future__ import annotations

import logging

import httpx

from app.settings import SPIDER_WORK_DOWNLOAD_CNT_URL, SPIDER_WORKS_URL

logger = logging.getLogger(__name__)


def fetch_works(
    start_date: str,
    end_date: str,
    page_size: int = 100,
) -> dict[str, int]:
    """拉取作品列表，返回 {番号: download_cnt}。"""
    works: dict[str, int] = {}
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
            for w in data.get("data") or []:
                code = (w.get("code") or "").strip()
                if code:
                    works[code] = int(w.get("download_cnt") or 0)
            total = data.get("total_pages") or 1
            logger.info("作品 API %s/%s 页", page, total)
            if page >= total:
                break
            page += 1
    return works


def fetch_codes(
    start_date: str,
    end_date: str,
    page_size: int = 100,
) -> list[str]:
    return list(fetch_works(start_date, end_date, page_size).keys())


def update_works_download_cnt(
    code: str,
    download_cnt: int,
    *,
    current_download_cnt: int | None = None,
) -> bool:
    """调用 spider 更新 download_cnt；与当前值相同则跳过 POST。"""
    code = code.strip()
    if not code:
        raise ValueError("code 不能为空")
    if current_download_cnt is not None and current_download_cnt == download_cnt:
        logger.info(
            "%s download_cnt 已为 %s，跳过 spider 更新",
            code,
            download_cnt,
        )
        return True
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                SPIDER_WORK_DOWNLOAD_CNT_URL,
                json={"code": code, "download_cnt": download_cnt},
                headers={"Content-Type": "application/json"},
            )
    except httpx.HTTPError as exc:
        logger.warning("%s 同步 download_cnt 请求失败: %s", code, exc)
        return False
    if resp.is_success:
        logger.debug("%s download_cnt=%s 已同步 spider", code, download_cnt)
        return True
    detail = (resp.text or "").strip()[:200]
    logger.warning(
        "%s 同步 download_cnt 失败 HTTP %s: %s",
        code,
        resp.status_code,
        detail or resp.reason_phrase,
    )
    return False
