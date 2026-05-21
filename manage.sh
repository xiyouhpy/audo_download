#!/bin/bash
# 用法: ./manage.sh {start|stop|restart|status}

cd "$(dirname "$0")" || exit 1

SERVICE_NAME="download"
LOG_DIR="./log"
PID_FILE="./${SERVICE_NAME}.pid"

mkdir -p "$LOG_DIR"

get_log_file() {
    echo "$LOG_DIR/${SERVICE_NAME}.log"
}

get_api_port() {
    local port="8084"
    if [ -f ".env" ]; then
        local val
        val=$(grep -E '^DOWNLOAD_API_PORT=' .env | tail -1 | cut -d= -f2 | tr -d ' "'\''')
        [ -n "$val" ] && port="$val"
    fi
    echo "$port"
}

resolve_python() {
    if [ -x "./venv/bin/python" ]; then
        echo "./venv/bin/python"
    elif command -v python3.11 >/dev/null 2>&1; then
        echo "python3.11"
    else
        echo "python3"
    fi
}

start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Service is already running (PID: $PID)"
            return 1
        fi
        rm -f "$PID_FILE"
    fi

    PY=$(resolve_python)
    if [ "$PY" = "./venv/bin/python" ] || [ -d "venv" ]; then
        if [ ! -x "./venv/bin/python" ]; then
            echo "venv 无效，请重建: rm -rf venv && python3.11 -m venv venv && ./venv/bin/pip install -r requirements.txt" >&2
            return 1
        fi
    fi

    PORT=$(get_api_port)
    LOG_FILE=$(get_log_file)
    nohup "$PY" -m uvicorn main_server:app --host 0.0.0.0 --port "$PORT" >> "$LOG_FILE" 2>&1 &
    PID=$!
    echo "$PID" > "$PID_FILE"
    sleep 1
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "启动失败，日志:" >&2
        tail -20 "$LOG_FILE" >&2
        rm -f "$PID_FILE"
        return 1
    fi
    echo "Started PID=$PID port=$PORT log=$LOG_FILE"
}

stop() {
    [ -f "$PID_FILE" ] || { echo "Not running"; return 1; }
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        kill -9 "$PID"
        echo "Stopped PID=$PID"
    else
        echo "Stale PID=$PID"
    fi
    rm -f "$PID_FILE"
}

status() {
    PORT=$(get_api_port)
    if [ -f "$PID_FILE" ] && ps -p "$(cat "$PID_FILE")" > /dev/null 2>&1; then
        echo "Running PID=$(cat "$PID_FILE") port=$PORT"
        return 0
    fi
    echo "Not running (port $PORT)"
    return 1
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) stop; sleep 2; start ;;
    status) status ;;
    *) echo "Usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
