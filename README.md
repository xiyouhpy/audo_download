# audo_download

本地抓取脚本：从 spider 拉番号 → 老王搜磁力 → 经 **my_spider** API 写入 `magnet_link`。

## 结构

```
audo_download/
├── cron_download.sh      # 定时抓取
├── xunlei_download.sh    # 迅雷下载（读 spider 链接列表 API）
├── app/
│   ├── cli.py            # 命令行入口
│   ├── settings.py       # spider 地址、抓取参数
│   ├── spider_client.py  # works / magnet_link（HTTP → my_spider）
│   ├── laowang.py        # Playwright 抓取
│   ├── parsers.py        # HTML / thunder 解析
│   └── service.py        # 抓取主流程
└── cron/
    └── xunlei_download.py
```

数据库与 API 在 sibling 项目 **`../my_spider`**（端口 8082），需先执行其 `init_database.sql`（含 `magnet_link` 表）。

## 依赖

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python -m playwright install chromium
```

`app/settings.py` 中配置 `SPIDER_HOST`（默认 `127.0.0.1:8082`）。

## 抓取

```bash
# 定时脚本：输出已在 log/cron_download.log
./cron_download.sh

# 手动抓取：日志写入 log/download.log（含 Playwright 等 stderr）
mkdir -p log
./venv/bin/python -m app.cli --start-date 2026-04-20 --end-date 2026-04-30 \
  >> log/download.log 2>&1

./venv/bin/python -m app.cli --codes MIDA-636 --start-date 2020-01-01 --end-date 2026-12-31 \
  >> log/download.log 2>&1

# 查看进度
tail -f log/download.log
```

默认不写终端；调试时可加 `--verbose` 或 `-v`。

日志：`log/download.log`（手动 CLI）、`log/cron_download.log`（定时脚本）

库内链接数 **大于** `SKIP_DOWNLOAD_IF_COUNT_OVER`（默认 3）的番号会跳过。

### 搜索翻页策略

- 最多翻 **5** 页（`MAX_SEARCH_PAGES`，CLI：`--max-search-pages`）
- 每页统计 panel 总数与符合条数（番号匹配且含 `.mp4`/`.mkv`）
- 若某页 **符合率 < 50%**（`SEARCH_PAGE_MIN_MATCH_RATIO`），停止继续翻页
- 首页无结果或站点总页数不足时也会提前结束

## 迅雷下载

```bash
./xunlei_download.sh
./xunlei_download.sh --dry-run
```

接口：`GET http://{SPIDER_HOST}/spider/magnet_link/links/list`

Windows 自动吊起迅雷可选安装 `pywin32`。

## 本仓库使用的 magnet_link 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/spider/magnet_link/update_by_code` | 按番号写入，并按库内链接总数同步 `works.download_cnt` |
| GET | `/spider/magnet_link/count?code=` | 统计 thunder 链接数 |
| GET | `/spider/magnet_link/links/list` | 列表筛选（分页，迅雷脚本用） |

更多查询接口见 my_spider 文档。
