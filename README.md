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

```bash
pip install -r requirements.txt
python3.11 -m playwright install chromium

cp .env.example .env
# 编辑 .env 填写 MYSQL_PASSWORD 等

mysql -u root -p auto_download < app/schema.mysql.sql

chmod +x cron_download.sh
```

## 运行

```bash
./cron_download.sh

# 指定日期
START_DATE=2026-04-20 END_DATE=2026-04-30 ./cron_download.sh

python3.11 cron/download_links.py --start-date 2026-04-20 --end-date 2026-04-30
```

日志：`tail -f log/cron_download.log`

## MySQL 表 `magnet_link`

- 有链接：`thunder_url` 有值
- 未命中：`thunder_url` 为 NULL，`miss_reason` 有说明

```sql
SELECT code, thunder_url, total_size_text FROM magnet_link
WHERE start_date = '2026-04-20' AND thunder_url IS NOT NULL;

SELECT code, miss_reason FROM magnet_link WHERE thunder_url IS NULL;
```
