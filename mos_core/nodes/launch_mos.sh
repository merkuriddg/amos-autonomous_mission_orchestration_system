#!/bin/bash
# ============================================
# MOS — Launch Script
# ============================================

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║     MOS — Mission Operating System       ║"
echo "  ║           Starting up...                 ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")/.."

# Check dependencies
python3 -c "import flask" 2>/dev/null || {
    echo "  [!] Missing deps. Running: pip3 install -r requirements.txt"
    pip3 install -r requirements.txt
}

echo "  [MOS] Starting web C2 console..."
echo "  [MOS] URL: http://localhost:5000"
echo "  [MOS] Login: commander / mavrix2026"
echo ""

python3 web/app.py
