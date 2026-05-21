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


class LinksResponse(BaseModel):
    code: str
    count: int
    min_size_gb: Optional[float] = None
    max_size_gb: Optional[float] = None
    links: list[LinkItem]
