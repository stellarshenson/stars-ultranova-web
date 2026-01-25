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
    --access-logfile - \
    >> server.log 2>&1 &
SERVER_PID=$!

# Save PID
echo $SERVER_PID > .server.pid

# Wait a moment for server to start
sleep 2

# Check if server is running
if ps -p $SERVER_PID > /dev/null 2>&1; then
    echo "Server started successfully (PID: $SERVER_PID)"
    echo "Log file: server.log"
    echo "URL: http://localhost:$PORT"
    echo ""
    echo "Proxy support: enabled (auto-detects X-Forwarded-Prefix)"
    echo "To stop the server, run: ./stop.sh"
else
    echo "Error: Server failed to start. Check server.log for details."
    rm .server.pid
    exit 1
fi
