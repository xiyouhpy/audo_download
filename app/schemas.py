from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LinkItem(BaseModel):
    code: str
    thunder_url: str
    total_size_text: Optional[str] = None
    size_bytes: int = Field(description="解析后的文件大小（字节）")
    size_gb: float = Field(description="文件大小（GB，1024 进制）")
    group_name: Optional[str] = None
    title: Optional[str] = None
    created_at: Optional[datetime] = Field(None, description="抓取入库时间")


class LinksResponse(BaseModel):
    code: str
    count: int
    min_size: Optional[float] = None
    max_size: Optional[float] = None
    links: list[LinkItem]


class LinkListResponse(BaseModel):
    count: int
    page: int
    page_size: int
    total_pages: int
    create_start: Optional[str] = None
    create_end: Optional[str] = None
    min_size: Optional[float] = None
    max_size: Optional[float] = None
    code: Optional[str] = None
    links: list[LinkItem]
