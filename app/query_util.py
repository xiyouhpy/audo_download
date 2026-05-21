"""查询参数校验与日期边界解析。"""


def parse_created_bound(value: str | None, *, end_of_day: bool = False) -> str | None:
    """支持 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS。"""
    if not value or not value.strip():
        return None
    text = value.strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return f"{text} 23:59:59" if end_of_day else f"{text} 00:00:00"
    return text


def validate_ranges(
    *,
    min_size: float | None,
    max_size: float | None,
    create_start: str | None,
    create_end: str | None,
) -> None:
    if (
        min_size is not None
        and max_size is not None
        and min_size > max_size
    ):
        raise ValueError("min_size 不能大于 max_size")
    if create_start and create_end and create_start > create_end:
        raise ValueError("create_start 不能晚于 create_end")
