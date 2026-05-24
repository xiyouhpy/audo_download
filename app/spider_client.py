"""通过 my_spider HTTP 接口读写 works、magnet_link。"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from app.settings import (
    SPIDER_MAGNET_LINK_COUNT_URL,
    SPIDER_MAGNET_LINK_LIST_URL,
    SPIDER_MAGNET_LINK_MISS_REASON_URL,
    SPIDER_MAGNET_LINK_UPDATE_URL,
    SPIDER_WORKS_URL,
)

logger = logging.getLogger(__name__)


@dataclass
class MagnetLinkUpdateResult:
    code: str
    links_inserted: int = 0
    download_cnt: int = 0
    works_api_ok: bool = False


def _with_client(
    client: httpx.Client | None,
    timeout: float,
    fn: Callable[[httpx.Client], Any],
) -> Any:
    if client is not None:
        return fn(client)
    with httpx.Client(timeout=timeout) as c:
        return fn(c)


def _fetch_all_pages(
    client: httpx.Client,
    url: str,
    params: dict[str, Any],
    *,
    items_key: str,
    log_label: str | None = None,
) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        resp = client.get(url, params={**params, "page": page})
        resp.raise_for_status()
        data = resp.json()
        items.extend(data.get(items_key) or [])
        total = int(data.get("total_pages") or 1)
        if log_label:
            logger.info("%s %s/%s 页", log_label, page, total)
        if page >= total:
            break
        page += 1
    return items


def fetch_works(
    start_date: str,
    end_date: str,
    page_size: int = 100,
    *,
    client: httpx.Client | None = None,
) -> dict[str, int]:
    """拉取作品列表，返回 {番号: download_cnt}。"""

    def _fetch(c: httpx.Client) -> dict[str, int]:
        rows = _fetch_all_pages(
            c,
            SPIDER_WORKS_URL,
            {
                "page_size": page_size,
                "start_date": start_date,
                "end_date": end_date,
                "order_by": "release_date",
                "order": "asc",
            },
            items_key="data",
            log_label="作品 API",
        )
        works: dict[str, int] = {}
        for w in rows:
            code = (w.get("code") or "").strip()
            if code:
                works[code] = int(w.get("download_cnt") or 0)
        return works

    return _with_client(client, 30.0, _fetch)


def fetch_all_links(
    client: httpx.Client,
    params: dict[str, Any],
    *,
    list_url: str = SPIDER_MAGNET_LINK_LIST_URL,
) -> list[dict]:
    return _fetch_all_pages(client, list_url, params, items_key="links")


def count_download_links(
    code: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 30.0,
) -> int:
    def _get(c: httpx.Client) -> int:
        resp = c.get(
            SPIDER_MAGNET_LINK_COUNT_URL,
            params={"code": code.strip()},
        )
        resp.raise_for_status()
        return int(resp.json().get("count") or 0)

    return _with_client(client, timeout, _get)


def fetch_miss_reasons(
    code: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 30.0,
) -> tuple[int, list[str]]:
    """返回 (miss 记录数, miss_reason 列表)。"""
    def _get(c: httpx.Client) -> tuple[int, list[str]]:
        resp = c.get(
            SPIDER_MAGNET_LINK_MISS_REASON_URL,
            params={"code": code.strip()},
        )
        resp.raise_for_status()
        data = resp.json()
        return int(data.get("count") or 0), list(data.get("miss_reasons") or [])

    return _with_client(client, timeout, _get)


def update_magnet_links_by_code(
    code: str,
    records: list[dict],
    *,
    start_date: str,
    end_date: str,
    works_download_cnt: int | None = None,
    client: httpx.Client | None = None,
    timeout: float = 60.0,
) -> MagnetLinkUpdateResult:
    """按番号写入 magnet_link（由 spider 服务落库并同步 download_cnt）。"""
    code = code.strip()
    if not code:
        raise ValueError("code 不能为空")

    payload = {
        "code": code,
        "start_date": start_date,
        "end_date": end_date,
        "records": records,
        "current_download_cnt": works_download_cnt,
    }

    def _post(c: httpx.Client) -> MagnetLinkUpdateResult:
        resp = c.post(SPIDER_MAGNET_LINK_UPDATE_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
        result = MagnetLinkUpdateResult(
            code=data.get("code", code),
            links_inserted=int(data.get("links_inserted") or 0),
            download_cnt=int(data.get("download_cnt") or 0),
            works_api_ok=bool(data.get("works_updated")),
        )
        if not result.works_api_ok:
            logger.warning("%s spider 未同步 download_cnt", code)
        return result

    return _with_client(client, timeout, _post)
