#!/bin/bash
# 从 spider /magnet_link/links/list 拉取 thunder 链接并吊起本机迅雷下载
# 示例：
#   ./xunlei_download.sh
#   MIN_SIZE=1.5 MAX_SIZE=6 ./xunlei_download.sh
#   MIN_SIZE=2 MAX_SIZE=8 ./xunlei_download.sh --codes MIDA-636
#   ./xunlei_download.sh --codes MIDA-636 --min-size 1.5 --max-size 6 --dry-run

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

PYTHON="${PYTHON:-python3.11}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python3
fi

if [ -x "./venv/bin/python" ]; then
  PYTHON="./venv/bin/python"
fi

ARGS=()
if [ -n "${MIN_SIZE:-}" ]; then ARGS+=(--min-size "$MIN_SIZE"); fi
if [ -n "${MAX_SIZE:-}" ]; then ARGS+=(--max-size "$MAX_SIZE"); fi
if [ -n "${CREATE_START:-}" ]; then ARGS+=(--create-start "$CREATE_START"); fi
if [ -n "${CREATE_END:-}" ]; then ARGS+=(--create-end "$CREATE_END"); fi

exec "$PYTHON" cron/xunlei_download.py "${ARGS[@]}" "$@"
