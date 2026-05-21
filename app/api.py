from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.db import MagnetDB
from app.links import build_link_list
from app.query_util import parse_created_bound, validate_ranges
from app.schemas import LinkListResponse, LinksResponse
from app.settings import MySQLConfig

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


def _check_ranges(**kwargs) -> None:
    try:
        validate_ranges(**kwargs)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/links", response_model=LinksResponse)
async def get_links_by_code(
    code: str = Query(..., min_length=1, description="番号"),
    min_size: Optional[float] = Query(None, ge=0, description="最小体积 GB（含）"),
    max_size: Optional[float] = Query(None, ge=0, description="最大体积 GB（含）"),
):
    _check_ranges(
        min_size=min_size,
        max_size=max_size,
        create_start=None,
        create_end=None,
    )
    try:
        with MagnetDB(MySQLConfig.from_env()) as db:
            rows = db.fetch_links_by_code(code)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc

    links = build_link_list(rows, min_size, max_size)
    return LinksResponse(
        code=code.strip(),
        count=len(links),
        min_size=min_size,
        max_size=max_size,
        links=links,
    )


@router.get("/links/list", response_model=LinkListResponse)
async def list_links(
    create_start: Optional[str] = Query(
        None, description="抓取入库起始时间，如 2026-05-01 或 2026-05-01 09:00:00"
    ),
    create_end: Optional[str] = Query(
        None, description="抓取入库截止时间（日期仅填 YYYY-MM-DD 时含当天全天）"
    ),
    min_size: Optional[float] = Query(None, ge=0, description="最小体积 GB（含）"),
    max_size: Optional[float] = Query(None, ge=0, description="最大体积 GB（含）"),
    code: Optional[str] = Query(None, description="番号（可选，精确/忽略横线匹配）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    cs = parse_created_bound(create_start, end_of_day=False)
    ce = parse_created_bound(create_end, end_of_day=True)
    _check_ranges(
        min_size=min_size,
        max_size=max_size,
        create_start=cs,
        create_end=ce,
    )

    try:
        with MagnetDB(MySQLConfig.from_env()) as db:
            rows = db.fetch_links(code=code, create_start=cs, create_end=ce)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc

    items = build_link_list(rows, min_size, max_size)
    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start : start + page_size]
    total_pages = (total + page_size - 1) // page_size if total else 0

    return LinkListResponse(
        count=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        create_start=create_start,
        create_end=create_end,
        min_size=min_size,
        max_size=max_size,
        code=code.strip() if code else None,
        links=page_items,
    )
