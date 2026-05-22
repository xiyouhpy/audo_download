import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GB = 1024**3

# --- 服务地址 host:port（部署时改这里）---
SPIDER_HOST = "127.0.0.1:8082"
DOWNLOAD_HOST = "127.0.0.1:8084"

# --- 对外 HTTP 接口（其它模块直接 import）---
SPIDER_WORKS_URL = f"http://{SPIDER_HOST}/spider/works"
SPIDER_WORK_DOWNLOAD_CNT_URL = f"http://{SPIDER_HOST}/spider/work/download_cnt"
AUTO_DOWNLOAD_LINKS_LIST_URL = f"http://{DOWNLOAD_HOST}/auto_download/links/list"

API_PREFIX = "/auto_download"

# 老王搜索
LAOWANG_URL = "https://laowangjz.top"

# MySQL
MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = 3306
MYSQL_USER = "hpy"
MYSQL_PASSWORD = "123456"
MYSQL_DATABASE = "web_spider"

# 抓取默认参数
MIN_SIZE_GB = 1.5
MAX_LINKS_PER_CODE = 20
DEFAULT_PAGE_SIZE = 100
REQUEST_DELAY_SEC = 2.0
# 库内该番号已有下载链接数超过此值则跳过抓取（视为已下载过）
SKIP_DOWNLOAD_IF_COUNT_OVER = 3


def gb_to_bytes(gb: float) -> int:
    return int(gb * GB)


@dataclass
class MySQLConfig:
    host: str = MYSQL_HOST
    port: int = MYSQL_PORT
    user: str = MYSQL_USER
    password: str = MYSQL_PASSWORD
    database: str = MYSQL_DATABASE
    charset: str = "utf8mb4"

    @classmethod
    def from_env(cls) -> "MySQLConfig":
        return cls()

    def validate(self) -> None:
        if self.password:
            return
        print(
            "MySQL 未配置密码。请在 app/settings.py 填写 MYSQL_PASSWORD，"
            "或使用 --mysql-password。",
            file=sys.stderr,
        )
        raise SystemExit(1)


@dataclass
class RunConfig:
    start_date: str
    end_date: str
    mysql: MySQLConfig
    works_page_size: int = DEFAULT_PAGE_SIZE
    laowang_url: str = LAOWANG_URL
    min_size_gb: float = MIN_SIZE_GB
    max_links_per_code: int = MAX_LINKS_PER_CODE
    request_delay_sec: float = REQUEST_DELAY_SEC
    headless: bool = True

    @property
    def min_size_bytes(self) -> int:
        return gb_to_bytes(self.min_size_gb)
