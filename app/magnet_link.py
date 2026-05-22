"""magnet_link 表按番号写入（独立功能，供抓取流程或其它调用方使用）。"""
from __future__ import annotations

from dataclasses import dataclass

from app.db import MagnetDB
from app.parsers import thunder_url_md5
from app.works import update_works_download_cnt


@dataclass
class MagnetLinkUpdateResult:
    """一次按番号更新的结果。"""

    code: str
    links_inserted: int = 0
    miss_inserted: int = 0
    works_api_ok: bool = False

    @property
    def total(self) -> int:
        return self.links_inserted + self.miss_inserted


def update_magnet_links_by_code(
    db: MagnetDB,
    code: str,
    records: list[dict],
    *,
    start_date: str,
    end_date: str,
) -> MagnetLinkUpdateResult:
    """按番号更新 ``magnet_link``：一次调用写入该 code 下全部数据（1 条或多条）。

    ``records`` 每项约定：

    - 含 ``thunder_url``：作为链接行 ``INSERT IGNORE``（按 ``thunder_url_md5`` 去重）
    - 无 ``thunder_url`` 且含 ``miss_reason``：作为未命中行 ``INSERT``

    所有行均使用参数 ``code`` 作为番号（忽略 record 内自带的 code 字段差异）。

    Args:
        db: 已打开的 ``MagnetDB`` 连接
        code: 番号
        records: 本番号待写入的记录列表（可 1 条或多条）
        start_date: 抓取任务起始日期
        end_date: 抓取任务结束日期

    Returns:
        本番号本次新增的链接条数、未命中条数；并成功调用 spider 更新 download_cnt
    """
    code = code.strip()
    if not code:
        raise ValueError("code 不能为空")
    if db._conn is None:
        raise RuntimeError("MagnetDB 未连接，请在 with MagnetDB(...) 内调用")

    link_rows: list[tuple] = []
    miss_rows: list[tuple] = []

    for r in records:
        url = (r.get("thunder_url") or "").strip()
        if url:
            link_rows.append(
                (
                    code,
                    url,
                    thunder_url_md5(url),
                    r.get("total_size_text"),
                    r.get("group_name"),
                    r.get("title"),
                    start_date,
                    end_date,
                )
            )
            continue
        reason = (r.get("miss_reason") or "").strip()
        if reason:
            miss_rows.append((code, reason, start_date, end_date))

    links_inserted = 0
    miss_inserted = 0

    with db._conn.cursor() as cur:
        if link_rows:
            cur.executemany(
                """INSERT IGNORE INTO magnet_link
                (code, thunder_url, thunder_url_md5, total_size_text,
                 group_name, title, start_date, end_date)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                link_rows,
            )
            links_inserted = cur.rowcount
        for row in miss_rows:
            cur.execute(
                """INSERT INTO magnet_link
                (code, thunder_url, miss_reason, start_date, end_date)
                VALUES (%s, NULL, %s, %s, %s)""",
                row,
            )
            miss_inserted += cur.rowcount

    update_works_download_cnt(code, links_inserted)

    return MagnetLinkUpdateResult(
        code=code,
        links_inserted=links_inserted,
        miss_inserted=miss_inserted,
        works_api_ok=True,
    )
