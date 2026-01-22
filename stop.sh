#!/bin/bash
# Stop Stars Nova Web server

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "Stopping Stars Nova Web server..."

# Check if PID file exists
if [ ! -f ".server.pid" ]; then
    echo "Error: No PID file found. Server may not be running."

    # Try to find and kill any running instances
    PIDS=$(pgrep -f "python -m backend.main" || true)
    if [ -n "$PIDS" ]; then
        echo "Found running server processes: $PIDS"
        echo "Killing them..."
        pkill -f "python -m backend.main"
        echo "Server stopped."
    else
        echo "No running server found."
    fi
    exit 0
fi

# Read PID
PID=$(cat .server.pid)

# Check if process is running
if ps -p $PID > /dev/null 2>&1; then
    # Stop the server
    kill $PID

    # Wait for process to stop (max 10 seconds)
    for i in {1..10}; do
        if ! ps -p $PID > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    # Force kill if still running
    if ps -p $PID > /dev/null 2>&1; then
        echo "Process did not stop gracefully, force killing..."
        kill -9 $PID
    fi

    echo "Server stopped (PID: $PID)"
else
    echo "Server process (PID: $PID) is not running."
fi

# Remove PID file
rm .server.pid

echo "Cleanup complete."
