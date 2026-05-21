import hashlib
from pathlib import Path

import pymysql
from pymysql.cursors import DictCursor
from pymysql.err import OperationalError

from app.parsers import normalize_code
from app.settings import PROJECT_ROOT, MySQLConfig

_SCHEMA = (PROJECT_ROOT / "app" / "schema.mysql.sql").read_text(encoding="utf-8")


def thunder_url_md5(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()


class MagnetDB:
    def __init__(self, cfg: MySQLConfig):
        self.cfg = cfg
        self._conn = None

    def __enter__(self):
        self._open()
        with self._conn.cursor() as cur:
            cur.execute(_SCHEMA)
        return self

    def __exit__(self, *args):
        if self._conn:
            self._conn.commit() if not args[0] else self._conn.rollback()
            self._conn.close()
            self._conn = None

    def _open(self):
        if self._conn:
            return
        try:
            srv = pymysql.connect(
                host=self.cfg.host,
                port=self.cfg.port,
                user=self.cfg.user,
                password=self.cfg.password or None,
                charset=self.cfg.charset,
            )
            with srv.cursor() as cur:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{self.cfg.database}` "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            srv.commit()
            srv.close()
            self._conn = pymysql.connect(
                host=self.cfg.host,
                port=self.cfg.port,
                user=self.cfg.user,
                password=self.cfg.password or None,
                database=self.cfg.database,
                charset=self.cfg.charset,
                cursorclass=DictCursor,
                autocommit=False,
            )
        except OperationalError as e:
            if e.args and e.args[0] == 1045:
                raise OperationalError(
                    1045, f"{e.args[1]} — 请检查 MYSQL_PASSWORD"
                ) from e
            raise

    def save_links(self, start: str, end: str, records: list[dict]) -> None:
        if not records:
            return
        rows = [
            (
                r["code"],
                r["thunder"],
                thunder_url_md5(r["thunder"]),
                r.get("total_size_text"),
                r.get("group_name"),
                r.get("title"),
                start,
                end,
            )
            for r in records
            if r.get("thunder")
        ]
        if not rows:
            return
        with self._conn.cursor() as cur:
            cur.executemany(
                """INSERT IGNORE INTO magnet_link
                (code, thunder_url, thunder_url_md5, total_size_text,
                 group_name, title, start_date, end_date)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                rows,
            )

    def save_miss(self, start: str, end: str, code: str, reason: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO magnet_link
                (code, thunder_url, miss_reason, start_date, end_date)
                VALUES (%s, NULL, %s, %s, %s)""",
                (code, reason, start, end),
            )

    def fetch_links_by_code(self, code: str) -> list[dict]:
        norm = normalize_code(code)
        with self._conn.cursor() as cur:
            cur.execute(
                """SELECT code, thunder_url, total_size_text, group_name, title, created_at
                FROM magnet_link
                WHERE thunder_url IS NOT NULL
                  AND (code = %s OR LOWER(REPLACE(code, '-', '')) = %s)
                ORDER BY id DESC""",
                (code.strip(), norm),
            )
            return list(cur.fetchall())
