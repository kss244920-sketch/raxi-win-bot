#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "=========================================================="
echo " Starting Thums Up Thunder Auto-Farm Bot (Keep-Alive Mode)"
echo "=========================================================="

while true; do
    echo "[$(date)] Starting thunder_bot.py..."
    python3 thunder_bot.py
    EXIT_CODE=$?
    echo "[$(date)] Bot stopped with exit code $EXIT_CODE."
    echo "[$(date)] Auto-restarting in 3 seconds (Press Ctrl+C to abort)..."
    sleep 3
done
