# auto_download

从作品 API 拉取番号 → 老王磁力搜索 → 写入 MySQL；FastAPI 按番号查询链接。

## 结构

```
auto_download/
├── main_server.py      # FastAPI 入口
├── manage.sh           # API 进程管理
├── cron_download.sh    # 定时抓取
├── app/
│   ├── settings.py     # 配置与环境变量
│   ├── db.py           # MySQL
│   ├── parsers.py      # HTML 解析、thunder/MD5
│   ├── laowang.py      # Playwright 抓取
│   ├── works.py        # 作品 API
│   ├── service.py      # 抓取主流程
│   ├── links.py        # 查询结果过滤排序
│   ├── schemas.py      # API 响应模型
│   ├── api.py          # HTTP 路由
│   ├── cli.py          # 抓取命令行
│   └── schema.mysql.sql
└── cron/download_links.py
```

## 首次部署

```bash
rm -rf venv
python3.11 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python -m playwright install chromium

cp .env.example .env   # 填写 MYSQL_PASSWORD 等
mysql -u root -p <库名> < app/schema.mysql.sql

chmod +x cron_download.sh manage.sh
```

## 运行

### 抓取

默认按作品 **发行日期 `release_date`** 筛选：**今天起连续 7 天**（含今天，至今天+6 天）。

```bash
./cron_download.sh
START_DATE=2026-04-20 END_DATE=2026-04-30 ./cron_download.sh
./venv/bin/python -m app.cli --start-date 2026-04-20 --end-date 2026-04-30
```

日志：`log/download.log`、`log/cron_download.log`

### 查询 API

```bash
./manage.sh start
curl "http://127.0.0.1:8084/health"

# 按番号查（体积可选）
curl "http://127.0.0.1:8084/links?code=JUFE-621&min_size=1.5&max_size=3"

# 抓取列表：按入库时间、体积、番号筛选（分页）
curl "http://127.0.0.1:8084/links/list?create_start=2026-05-01&create_end=2026-05-21"
curl "http://127.0.0.1:8084/links/list?min_size=1.5&max_size=3&page=1&page_size=50"
curl "http://127.0.0.1:8084/links/list?create_start=2026-05-20&code=JUFE-621"
```

端口：`.env` 中 `DOWNLOAD_API_PORT`（默认 8084）。

### 吊起迅雷下载

从 `links/list` 拉取链接，**默认自动确认并立即开始下载**（`--method auto`）：

| 平台 | 行为 |
|------|------|
| Windows | COM：`AddTask` 立即开始 + `CommitTasks2(1)` 静默提交（需 `pip install pywin32`） |
| macOS | 写入迅雷静默偏好 + 打开 `magnet://`（无需辅助功能）；可选 `--mac-ui-confirm` 自动点确认 |

```bash
chmod +x xunlei_download.sh

# 默认 http://101.42.12.171:8084，1.5~6 GB，自动确认
./xunlei_download.sh

# 只预览
./xunlei_download.sh --dry-run

# 改用其它 API 地址时
DOWNLOAD_API_BASE=http://127.0.0.1:8084 ./xunlei_download.sh

# 恢复旧行为（会弹出迅雷确认框）
./xunlei_download.sh --no-auto --method open
```

**Windows 额外建议**：迅雷 → 工具 → 配置 → 高级，取消「通过 IE 右键…添加任务」勾选，可减少确认弹窗。

**macOS**：脚本会写入 `showNewTaskPanel=false` 等偏好；若仍弹确认窗请**重启迅雷**一次。只有使用 `--mac-ui-confirm` 时才需在「辅助功能」里勾选终端。

## 表 `magnet_link`

| 场景 | 说明 |
|------|------|
| 有链接 | `thunder_url` + `thunder_url_md5`，唯一索引去重，`INSERT IGNORE` |
| 未命中 | `thunder_url` 为 NULL，`miss_reason` 有说明 |
