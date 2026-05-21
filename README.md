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
curl "http://127.0.0.1:8084/links?code=JUFE-621&min_size_gb=1.5&max_size_gb=3"
```

端口：`.env` 中 `DOWNLOAD_API_PORT`（默认 8084）。

## 表 `magnet_link`

| 场景 | 说明 |
|------|------|
| 有链接 | `thunder_url` + `thunder_url_md5`，唯一索引去重，`INSERT IGNORE` |
| 未命中 | `thunder_url` 为 NULL，`miss_reason` 有说明 |
