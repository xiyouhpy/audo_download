#!/bin/bash
# 定时下载磁力链接并写入 MySQL
# START_DATE=2026-04-20 END_DATE=2026-04-30 ./cron_download.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

PYTHON="${PYTHON:-python3.11}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python3
fi

LOG_FILE="./log/cron_download.log"
mkdir -p "$(dirname "$LOG_FILE")"

# 默认：发行日期为今天起连续 7 天（含今天，至今天+6）
START_DATE="${START_DATE:-$(date +%Y-%m-%d)}"
END_DATE="${END_DATE:-$(date -d '+6 days' +%Y-%m-%d 2>/dev/null || date -v+6d +%Y-%m-%d)}"

echo "=========================================" >> "$LOG_FILE"
echo "下载任务开始 - $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "日期范围: $START_DATE ~ $END_DATE" >> "$LOG_FILE"

"$PYTHON" cron/download_links.py \
  --start-date "$START_DATE" \
  --end-date "$END_DATE" \
  >> "$LOG_FILE" 2>&1

STATUS=$?
if [ $STATUS -eq 0 ]; then
  echo "下载任务成功 - $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
else
  echo "下载任务失败 exit=$STATUS - $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
fi
echo "=========================================" >> "$LOG_FILE"
exit $STATUS
