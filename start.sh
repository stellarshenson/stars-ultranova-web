#!/bin/bash
# Start Stars Nova Web server with gunicorn (proxy-aware)

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Load settings from project.env
source project.env 2>/dev/null || true

# Server configuration
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-9800}
WORKERS=${WORKERS:-1}
FORWARDED_ALLOW_IPS=${FORWARDED_ALLOW_IPS:-*}

# GameManager keeps per-process state (_game_cache, _last_messages);
# multiple workers would each hold a divergent copy and corrupt games.
if [ "$WORKERS" -gt 1 ]; then
    echo "Error: WORKERS=$WORKERS is not supported - GameManager caches game state per process (_game_cache/_last_messages). Use WORKERS=1."
    exit 1
fi

echo "Starting Stars Nova Web server..."

# Check if server is already running
if [ -f ".server.pid" ]; then
    PID=$(cat .server.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Error: Server is already running (PID: $PID)"
        exit 1
    else
        # Stale PID file
        rm .server.pid
    fi
fi

# Start server in background with gunicorn
# - uvicorn.workers.UvicornWorker for async support
# - --forwarded-allow-ips to trust proxy headers from any IP
# - --access-logfile for request logging
export FORWARDED_ALLOW_IPS="$FORWARDED_ALLOW_IPS"
nohup uv run gunicorn backend.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers $WORKERS \
    --bind $HOST:$PORT \
    --forwarded-allow-ips "$FORWARDED_ALLOW_IPS" \
    --pid .server.pid \
    --access-logfile - \
    >> server.log 2>&1 &

# Wait for the server to answer /health (up to ~30s)
READY=0
for i in {1..60}; do
    if curl -sf "http://127.0.0.1:$PORT/health" > /dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 0.5
done

if [ "$READY" -eq 1 ]; then
    # gunicorn writes .server.pid itself (asynchronously) - tolerate
    # a brief delay before the file appears
    for i in {1..10}; do
        [ -f ".server.pid" ] && break
        sleep 0.5
    done
    SERVER_PID=$(cat .server.pid 2>/dev/null || echo "unknown")
    echo "Server started successfully (PID: $SERVER_PID)"
    echo "Log file: server.log"
    echo "URL: http://localhost:$PORT"
    echo ""
    echo "Proxy support: enabled (auto-detects X-Forwarded-Prefix)"
    echo "To stop the server, run: ./stop.sh"
else
    echo "Error: Server failed to start. Check server.log for details."
    tail -n 20 server.log
    exit 1
fi
