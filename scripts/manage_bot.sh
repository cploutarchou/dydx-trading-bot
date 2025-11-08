#!/bin/bash

# Script to manage the dYdX trading bot

case "$1" in
    "start")
        echo "Starting dYdX trading bot..."
        cd "$(dirname "$0")/.."
        source .venv/bin/activate
        python app/main.py
        ;;
    "stop")
        echo "Stopping dYdX trading bot..."
        # Find and kill the bot process
        PIDS=$(ps aux | grep "python.*main.py" | grep -v grep | awk '{print $2}')
        if [ -z "$PIDS" ]; then
            echo "No dYdX bot processes found running."
        else
            echo "Found bot processes: $PIDS"
            for PID in $PIDS; do
                echo "Killing process $PID..."
                kill -TERM "$PID"
                sleep 2
                # If the process is still running, force kill it
                if ps -p "$PID" > /dev/null 2>&1; then
                    echo "Process $PID still running, force killing..."
                    kill -KILL "$PID"
                fi
            done
            echo "Bot stopped."
        fi
        ;;
    "status")
        echo "Checking dYdX trading bot status..."
        PIDS=$(ps aux | grep "python.*main.py" | grep -v grep | awk '{print $2}')
        if [ -z "$PIDS" ]; then
            echo "dYdX bot is not running."
        else
            echo "dYdX bot is running with PID(s): $PIDS"
        fi
        ;;
    "restart")
        echo "Restarting dYdX trading bot..."
        $0 stop
        sleep 3
        $0 start
        ;;
    *)
        echo "Usage: $0 {start|stop|status|restart}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the dYdX trading bot"
        echo "  stop    - Stop the dYdX trading bot"
        echo "  status  - Check if the bot is running"
        echo "  restart - Restart the bot"
        exit 1
        ;;
esac