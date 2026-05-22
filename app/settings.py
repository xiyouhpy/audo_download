from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GB = 1024**3

# --- my_spider 服务地址（部署时改这里）---
SPIDER_HOST = "101.42.12.171:8082"

# --- spider HTTP 接口 ---
SPIDER_WORKS_URL = f"http://{SPIDER_HOST}/spider/works"
SPIDER_MAGNET_LINK_UPDATE_URL = (
    f"http://{SPIDER_HOST}/spider/magnet_link/update_by_code"
)
SPIDER_MAGNET_LINK_COUNT_URL = f"http://{SPIDER_HOST}/spider/magnet_link/count"
SPIDER_MAGNET_LINK_LIST_URL = f"http://{SPIDER_HOST}/spider/magnet_link/links/list"

# 老王搜索
LAOWANG_URL = "https://laowangjz.top"

# 抓取默认参数
MIN_SIZE_GB = 1.5
MAX_LINKS_PER_CODE = 20
MAX_SEARCH_PAGES = 5
# 单页符合率低于此比例时停止继续翻页（超过一半不符合预期）
SEARCH_PAGE_MIN_MATCH_RATIO = 0.5
DEFAULT_PAGE_SIZE = 100
XUNLEI_LIST_PAGE_SIZE = 50
REQUEST_DELAY_SEC = 2.0
SKIP_DOWNLOAD_IF_COUNT_OVER = 3


def gb_to_bytes(gb: float) -> int:
    return int(gb * GB)


@dataclass
class RunConfig:
    start_date: str
    end_date: str
    works_page_size: int = DEFAULT_PAGE_SIZE
    laowang_url: str = LAOWANG_URL
    min_size_gb: float = MIN_SIZE_GB
    max_links_per_code: int = MAX_LINKS_PER_CODE
    max_search_pages: int = MAX_SEARCH_PAGES
    request_delay_sec: float = REQUEST_DELAY_SEC
    headless: bool = True

    @property
    def min_size_bytes(self) -> int:
        return gb_to_bytes(self.min_size_gb)
