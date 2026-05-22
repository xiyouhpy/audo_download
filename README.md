# auto_download

从作品 API 拉取番号 → 老王磁力搜索 → 写入 MySQL；FastAPI 按番号查询链接。

## 结构

```
auto_download/
├── main_server.py      # FastAPI 入口
├── manage.sh           # API 进程管理
├── cron_download.sh    # 定时抓取
├── app/
│   ├── settings.py     # 地址、接口 URL、MySQL、抓取参数
│   ├── db.py           # MySQL 连接与查询
│   ├── magnet_link.py  # 按番号更新 magnet_link，并调 spider 同步 download_cnt
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

# VM/本机环境自检（务必用与抓取相同的 python）
./venv/bin/python scripts/check_env.py

# 编辑 app/settings.py：MYSQL_PASSWORD、SPIDER_HOST、DOWNLOAD_HOST 等
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

**VM 抓取无结果时**：先 `python3 scripts/check_env.py`（或 `./venv/bin/python`）；确认 Chromium 已安装。搜索失败时会在 `log/laowang_debug/` 保存 HTML 快照，日志含 `signals=`、`challenge=` 字段。勿混用系统 `python3` 与 venv（Playwright 浏览器按解释器安装）。

抓取任务**每处理完一个番号立即提交 MySQL**（无需全部跑完），日志可见 `已提交 MySQL`。

服务地址与接口 URL 均在 `app/settings.py` 顶部配置（改 `SPIDER_HOST` / `DOWNLOAD_HOST` 等即可）。

抓取时若某番号在 `magnet_link` 中已有下载链接数 **大于** `SKIP_DOWNLOAD_IF_COUNT_OVER`（默认 3），则跳过该番号。

### 查询 API

URL 规则与 spider 服务相同（`/服务名/资源`），本服务前缀为 **`/auto_download`**（对照 `http://101.42.12.171:8082/spider/works`）。

```bash
./manage.sh start
curl "http://127.0.0.1:8084/auto_download/health"

# 按番号查列表（路径参数 + 分页）
curl "http://127.0.0.1:8084/auto_download/links/code/SNOS-239"
curl "http://127.0.0.1:8084/auto_download/links/code/SNOS239?min_size=1.5&max_size=6&page=1&page_size=50"

# 按番号查（query 参数，全量不分页）
curl "http://127.0.0.1:8084/auto_download/links?code=JUFE-621&min_size=1.5&max_size=3"

# 链接列表：按入库时间、体积、番号筛选（分页）
curl "http://127.0.0.1:8084/auto_download/links/list?create_start=2026-05-01&create_end=2026-05-21"
curl "http://127.0.0.1:8084/auto_download/links/list?min_size=1.5&max_size=3&page=1&page_size=50"
curl "http://127.0.0.1:8084/auto_download/links/list?code=JUFE-621"
```

| 接口 | 说明 |
|------|------|
| `GET /auto_download/health` | 健康检查 |
| `GET /auto_download/links/code/{code}` | 按番号查列表（忽略横线、大小写），支持体积筛选与分页 |
| `GET /auto_download/links?code=` | 按番号查，一次返回全部链接 |
| `GET /auto_download/links/list` | 全库列表，可选 `code`、入库时间、体积筛选 |

监听端口：8084（在 `main_server.py` 中启动）；客户端访问地址见 `DOWNLOAD_HOST`（如 `127.0.0.1:8084`）。

### 吊起迅雷下载

从 `/auto_download/links/list` 拉取链接，**按番号分组**：同一番号多条一次提交迅雷（Windows COM 批量）。默认自动确认并立即开始（`--method auto`）：

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

# 改地址见 app/settings.py

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
