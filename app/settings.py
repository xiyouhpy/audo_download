import os
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

WORKS_API_BASE = "http://101.42.12.171:8082/spider/works"
LAOWANG_BASE_URL = "https://laowangjz.top"
MIN_SIZE_GB = 1.5
MAX_LINKS_PER_CODE = 20
DEFAULT_PAGE_SIZE = 100
REQUEST_DELAY_SEC = 2.0


def load_dotenv() -> None:
    path = PROJECT_ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class MySQLConfig:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "auto_download"
    charset: str = "utf8mb4"

    @classmethod
    def from_env(cls) -> "MySQLConfig":
        return cls(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "auto_download"),
        )

    def validate(self) -> None:
        if self.password:
            return
        print(
            "MySQL 未配置密码。请在项目根目录创建 .env 并填写 MYSQL_PASSWORD，"
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
    laowang_base_url: str = LAOWANG_BASE_URL
    min_size_gb: float = MIN_SIZE_GB
    min_size_bytes: int = int(MIN_SIZE_GB * 1024**3)
    max_links_per_code: int = MAX_LINKS_PER_CODE
    request_delay_sec: float = REQUEST_DELAY_SEC
    headless: bool = True
    works_api_base: str = WORKS_API_BASE
