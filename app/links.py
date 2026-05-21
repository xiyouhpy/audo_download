from app.parsers import parse_size
from app.schemas import LinkItem
from app.settings import GB, gb_to_bytes


def build_link_list(
    rows: list[dict],
    min_size: float | None = None,
    max_size: float | None = None,
) -> list[LinkItem]:
    min_bytes = gb_to_bytes(min_size) if min_size is not None else None
    max_bytes = gb_to_bytes(max_size) if max_size is not None else None

    items: list[LinkItem] = []
    for row in rows:
        url = row.get("thunder_url") or ""
        if not url:
            continue
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
                created_at=row.get("created_at"),
            )
        )

    items.sort(key=lambda x: (x.size_bytes, x.thunder_url))
    return items
