#!/bin/bash
set -e
echo "Patching navigation into existing pages..."

TEMPLATES=~/mos_ws/src/mos_c2_console/mos_c2_console/templates

# Patch every existing HTML file that has a nav section
for FILE in $TEMPLATES/index.html $TEMPLATES/dashboard.html $TEMPLATES/awacs.html \
           $TEMPLATES/tactical3d.html $TEMPLATES/echelon.html $TEMPLATES/hal.html; do
  if [ -f "$FILE" ]; then
    # Check if EW link already exists
    if grep -q '"/ew"' "$FILE" 2>/dev/null; then
      echo "  [skip] $(basename $FILE) already has EW links"
    else
      # Find the nav section and inject the new links
      # Strategy: look for </div> after nav links and inject before it
      # Or simply add a universal top-bar if nav not found

      # Try to add links after existing nav links (look for /awacs or /dashboard patterns)
      if grep -q 'href="/awacs"' "$FILE"; then
        sed -i 's|href="/awacs">AWACS</a>|href="/awacs">AWACS</a>\
    <a href="/ew" style="color:\#ff0066">⚡EW</a>\
    <a href="/sigint">📡SIGINT</a>\
    <a href="/cyber">🔓CYBER</a>|' "$FILE"
        echo "  [+] $(basename $FILE) patched (after AWACS link)"
      elif grep -q 'href="/dashboard"' "$FILE"; then
        sed -i 's|href="/dashboard">|href="/ew" style="color:\#ff0066">⚡EW</a>\
    <a href="/sigint">📡SIGINT</a>\
    <a href="/cyber">🔓CYBER</a>\
    <a href="/dashboard">|' "$FILE"
        echo "  [+] $(basename $FILE) patched (before dashboard link)"
      else
        echo "  [!] $(basename $FILE) — no nav pattern found, adding floating nav"
        # Inject a floating nav bar at top of body
        sed -i '/<body/a\
<div style="position:fixed;top:0;left:0;right:0;z-index:9999;background:#0a0a0aee;\
padding:4px 15px;font-family:monospace;font-size:11px;border-bottom:1px solid #ff006644;\
display:flex;gap:12px;align-items:center">\
<span style="color:#ff0066;font-weight:bold">MOS</span>\
<a href="/" style="color:#00ccff;text-decoration:none">C2 Map</a>\
<a href="/dashboard" style="color:#00ccff;text-decoration:none">Digital Twin</a>\
<a href="/ew" style="color:#ff0066;text-decoration:none;font-weight:bold">⚡ EW/SIGINT</a>\
<a href="/sigint" style="color:#00ccff;text-decoration:none">📡 SIGINT DB</a>\
<a href="/cyber" style="color:#00ccff;text-decoration:none">🔓 Cyber</a>\
<a href="/awacs" style="color:#00ccff;text-decoration:none">AWACS</a>\
<a href="/tactical3d" style="color:#00ccff;text-decoration:none">3D</a>\
<a href="/echelon" style="color:#00ccff;text-decoration:none">Echelon</a>\
<a href="/hal" style="color:#00ccff;text-decoration:none">HAL</a>\
</div>\
<div style="height:28px"></div>' "$FILE"
        echo "  [+] $(basename $FILE) — floating nav injected"
      fi
    fi
  fi
done

echo ""
echo "✅ Navigation patched. All pages now link to EW/SIGINT/Cyber."
echo ""
echo "Full site map:"
echo "  /           → C2 Map (main view)"
echo "  /dashboard  → Digital Twin"
echo "  /ew         → ⚡ EW Dashboard (spectrum + waterfall + emitter map)"
echo "  /sigint     → 📡 SIGINT Database (signals table + analysis)"
echo "  /cyber      → 🔓 Cyber Operations (WiFi + devices + vulns + IDS)"
echo "  /awacs      → AWACS View"
echo "  /tactical3d → 3D Tactical"
echo "  /echelon    → Echelon"
echo "  /hal        → HAL AI"
