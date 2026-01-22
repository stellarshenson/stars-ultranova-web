#!/bin/bash
# Start Stars Nova Web server

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

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

# Start server in background
nohup uv run python -m backend.main >> server.log 2>&1 &
SERVER_PID=$!

# Save PID
echo $SERVER_PID > .server.pid

# Wait a moment for server to start
sleep 2

# Check if server is running
if ps -p $SERVER_PID > /dev/null 2>&1; then
    echo "Server started successfully (PID: $SERVER_PID)"
    echo "Log file: server.log"
    echo "URL: http://localhost:9800"
    echo ""
    echo "To stop the server, run: ./stop.sh"
else
    echo "Error: Server failed to start. Check server.log for details."
    rm .server.pid
    exit 1
fi
