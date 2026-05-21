"""磁力链接查询 API（FastAPI）。"""
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.db import MagnetDB
from app.parsers import parse_size
from app.settings import MySQLConfig, load_dotenv

GB = 1024**3


class LinkItem(BaseModel):
    code: str
    thunder_url: str
    total_size_text: Optional[str] = None
    size_bytes: int = Field(..., description="解析后的文件大小（字节）")
    size_gb: float = Field(..., description="文件大小（GB，1024 进制）")
    group_name: Optional[str] = None
    title: Optional[str] = None


class LinksResponse(BaseModel):
    code: str
    count: int
    min_size_gb: Optional[float] = None
    max_size_gb: Optional[float] = None
    links: list[LinkItem]


def _filter_and_sort(
    rows: list[dict],
    min_size_gb: Optional[float],
    max_size_gb: Optional[float],
) -> list[LinkItem]:
    seen: set[str] = set()
    items: list[LinkItem] = []
    min_bytes = int(min_size_gb * GB) if min_size_gb is not None else None
    max_bytes = int(max_size_gb * GB) if max_size_gb is not None else None

    for row in rows:
        url = row.get("thunder_url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        size_bytes = parse_size(row.get("total_size_text") or "")
        if min_bytes is not None and size_bytes < min_bytes:
            continue
        if max_bytes is not None and size_bytes > max_bytes:
            continue
        items.append(
            LinkItem(
                code=row["code"],
                thunder_url=url,
                total_size_text=row.get("total_size_text"),
                size_bytes=size_bytes,
                size_gb=round(size_bytes / GB, 3) if size_bytes else 0.0,
                group_name=row.get("group_name"),
                title=row.get("title"),
            )
        )

    items.sort(key=lambda x: (x.size_bytes, x.thunder_url))
    return items


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()
    yield


app = FastAPI(title="auto_download API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/links", response_model=LinksResponse)
async def get_links(
    code: str = Query(..., min_length=1, description="番号"),
    min_size_gb: Optional[float] = Query(
        None, ge=0, description="最小文件大小（GB），含边界"
    ),
    max_size_gb: Optional[float] = Query(
        None, ge=0, description="最大文件大小（GB），含边界"
    ),
):
    if (
        min_size_gb is not None
        and max_size_gb is not None
        and min_size_gb > max_size_gb
    ):
        raise HTTPException(
            status_code=400,
            detail="min_size_gb 不能大于 max_size_gb",
        )

    cfg = MySQLConfig.from_env()
    try:
        with MagnetDB(cfg) as db:
            rows = db.fetch_links_by_code(code)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    links = _filter_and_sort(rows, min_size_gb, max_size_gb)
    return LinksResponse(
        code=code.strip(),
        count=len(links),
        min_size_gb=min_size_gb,
        max_size_gb=max_size_gb,
        links=links,
    )


if __name__ == "__main__":
    import uvicorn

    load_dotenv()
    port = int(os.getenv("DOWNLOAD_API_PORT", "8084"))
    uvicorn.run(
        "main_server:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("DOWNLOAD_API_RELOAD", "").lower() in ("1", "true", "yes"),
    )
