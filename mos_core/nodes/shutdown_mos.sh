#!/bin/bash
echo "[MOS] Shutting down..."
pkill -f "python3 web/app.py" 2>/dev/null
echo "[MOS] Stopped."
