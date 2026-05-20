#!/bin/bash

# 服务管理脚本
# 使用方法：./manage.sh {start|stop|restart}

# 配置变量
SERVICE_NAME="download"
# shellcheck disable=SC2034
PYTHON_APP="main_server.py"   # FastAPI 入口
LOG_DIR="./log"               # 日志目录
PID_FILE="./$SERVICE_NAME.pid" # PID 文件路径

# 创建日志目录
mkdir -p "$LOG_DIR"

# 生成带时间戳的日志文件名
get_log_file() {
    # echo "$LOG_DIR/${SERVICE_NAME}_$(date +%Y%m%d%H%M%S).log"
    echo "$LOG_DIR/${SERVICE_NAME}.log"
}

start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Service is already running (PID: $PID)"
            return 1
        else
            echo "Removing stale PID file..."
            rm -f "$PID_FILE"
        fi
    fi

    # 启动服务并重定向日志
    LOG_FILE=$(get_log_file)
    if [ -d "venv" ]; then
        if [ ! -x "./venv/bin/python" ]; then
            echo "venv 已失效或 Python 版本不对，请重建：" >&2
            echo "  rm -rf venv && python3.11 -m venv venv && ./venv/bin/pip install -r requirements.txt" >&2
            return 1
        fi
        PY="./venv/bin/python"
    else
        PY="python3.11"
    fi
    nohup "$PY" "$PYTHON_APP" >> "$LOG_FILE" 2>&1 &
    PID=$!

    # 写入 PID 文件
    echo $PID > "$PID_FILE"
    echo "Service started (PID: $PID)"
    echo "Log output: $LOG_FILE"
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "PID file not found. Service may not be running."
        return 1
    fi

    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        kill -9 "$PID"
        echo "Service stopped (PID: $PID)"
        rm -f "$PID_FILE"
    else
        echo "Service not running (PID: $PID)"
        rm -f "$PID_FILE"
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 2
        start
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
esac

exit 0
