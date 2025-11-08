#!/bin/bash
# Quick test script to verify the bot can be started and stopped

cd "$(dirname "$0")/.."

echo "Testing bot startup and shutdown..."

# Start the bot in background
source .venv/bin/activate
python app/main.py &
BOT_PID=$!

echo "Bot started with PID: $BOT_PID"

# Wait 3 seconds
sleep 3

# Check if bot is still running
if ps -p "$BOT_PID" > /dev/null 2>&1; then
    echo "Bot is running, sending SIGTERM..."
    kill -TERM "$BOT_PID"
    
    # Wait for graceful shutdown
    sleep 2
    
    # Check if it's still running
    if ps -p "$BOT_PID" > /dev/null 2>&1; then
        echo "Bot didn't stop gracefully, force killing..."
        kill -KILL "$BOT_PID"
    else
        echo "Bot stopped gracefully!"
    fi
else
    echo "Bot already stopped (may have encountered an error)"
fi

echo "Test completed."