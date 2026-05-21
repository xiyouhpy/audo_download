from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.db import MagnetDB
from app.links import build_link_list
from app.schemas import LinksResponse
from app.settings import MySQLConfig

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/links", response_model=LinksResponse)
async def get_links(
    code: str = Query(..., min_length=1, description="番号"),
    min_size_gb: Optional[float] = Query(None, ge=0, description="最小体积 GB（含）"),
    max_size_gb: Optional[float] = Query(None, ge=0, description="最大体积 GB（含）"),
):
    if (
        min_size_gb is not None
        and max_size_gb is not None
        and min_size_gb > max_size_gb
    ):
        raise HTTPException(400, "min_size_gb 不能大于 max_size_gb")

    try:
        with MagnetDB(MySQLConfig.from_env()) as db:
            rows = db.fetch_links_by_code(code)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc

    links = build_link_list(rows, min_size_gb, max_size_gb)
    return LinksResponse(
        code=code.strip(),
        count=len(links),
        min_size_gb=min_size_gb,
        max_size_gb=max_size_gb,
        links=links,
    )
