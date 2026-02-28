#!/bin/bash
# Kill all running LibreOffice processes.

PROCESSES=("soffice" "soffice.bin" "oosplash")
killed=0

for name in "${PROCESSES[@]}"; do
    while IFS= read -r pid; do
        [ -z "$pid" ] && continue
        echo "[OK] Killing $name (PID $pid)"
        kill -9 "$pid" 2>/dev/null
        ((killed++))
    done < <(pgrep -x "$name" 2>/dev/null)
done

if [ "$killed" -eq 0 ]; then
    echo "[OK] No LibreOffice process running."
else
    echo "[OK] Killed $killed process(es)."
fi
