import logging

import httpx

from app.settings import WORKS_API_BASE

logger = logging.getLogger(__name__)


def fetch_codes(
    start_date: str,
    end_date: str,
    page_size: int = 100,
    api_base: str = WORKS_API_BASE,
) -> list[str]:
    codes = []
    page = 1
    with httpx.Client(timeout=30.0) as client:
        while True:
            resp = client.get(
                api_base,
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
