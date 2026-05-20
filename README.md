# auto_download

从作品 API 拉取番号 → 老王磁力搜索 → **写入 MySQL**。

## 结构

```
auto_download/
├── app/
│   ├── settings.py
│   ├── db.py
│   ├── parsers.py
│   ├── works.py
│   ├── laowang.py
│   ├── service.py
│   └── schema.mysql.sql
├── cron/download_links.py
├── cron_download.sh
└── .env
```

## 首次部署

项目使用 **Python 3.11**。若 `venv` 里解释器版本不对或符号链接已断（例如曾用 3.14 创建后又卸载），删掉重建即可：

```bash
rm -rf venv
python3.11 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python -m playwright install chromium

cp .env.example .env
# 编辑 .env 填写 MYSQL_PASSWORD 等

mysql -u root -p auto_download < app/schema.mysql.sql

chmod +x cron_download.sh manage.sh
```

## 运行

### 定时抓取

```bash
./cron_download.sh

# 指定日期
START_DATE=2026-04-20 END_DATE=2026-04-30 ./cron_download.sh

./venv/bin/python cron/download_links.py --start-date 2026-04-20 --end-date 2026-04-30
```

日志：`tail -f log/cron_download.log`

### 查询 API（FastAPI）

```bash
./manage.sh start      # 后台启动，PID 写入 download.pid
./manage.sh stop
./manage.sh restart

tail -f log/download.log
```

默认端口 `8083`，可在 `.env` 设置 `DOWNLOAD_API_PORT`。

```bash
curl "http://127.0.0.1:8083/links?code=SONE-123"
curl "http://127.0.0.1:8083/links?code=SONE-123&min_size_gb=1.5&max_size_gb=3"
```

## MySQL 表 `magnet_link`

- 有链接：`thunder_url` 有值
- 未命中：`thunder_url` 为 NULL，`miss_reason` 有说明

```sql
SELECT code, thunder_url, total_size_text FROM magnet_link
WHERE start_date = '2026-04-20' AND thunder_url IS NOT NULL;

SELECT code, miss_reason FROM magnet_link WHERE thunder_url IS NULL;
```
