#!/usr/bin/env bash
# Run install on a WSL distro with log file + live tail (host-side helper).
set -euo pipefail

DISTRO="${1:-MARISDeployTest}"
LOG="${2:-/tmp/maris-deploy-${DISTRO}.log}"
OPENAI_KEY="${OPENAI_API_KEY:-}"

if [[ -z "$OPENAI_KEY" && -f /home/ma-agent1/projects/SUP_QA_Helper/.env ]]; then
  OPENAI_KEY=$(python3 -c "
from pathlib import Path
for line in Path('/home/ma-agent1/projects/SUP_QA_Helper/.env').read_text().splitlines():
    if line.startswith('OPENAI_API_KEY=') and 'placeholder' not in line.lower():
        print(line.split('=', 1)[1].strip())
        break
")
fi

: >"$LOG"
echo "Log: $LOG"

wsl.exe -d "$DISTRO" -- bash -lc "
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
rm -rf /root/projects/SUP_QA_Helper
git clone https://github.com/sealsnipe/MARIS_QA_Helper.git /root/projects/SUP_QA_Helper
cd /root/projects/SUP_QA_Helper
chmod +x install.sh setup.sh scripts/update.sh
./install.sh --non-interactive --profile prod --runtime docker --llm-auth-mode api_key --openai-key '$OPENAI_KEY' --start
curl -sf http://127.0.0.1:8088/api/health
echo
SEED_ADMIN_PASSWORD=xxxxxxxx python3 scripts/seed_production.py
echo MARIS_DEPLOY_OK
" >>"$LOG" 2>&1 &

PID=$!
echo "Deploy PID: $PID (WSL background)"

while kill -0 "$PID" 2>/dev/null; do
  sleep 15
  echo "--- $(date '+%H:%M:%S') ---"
  tail -n 8 "$LOG" || true
done

wait "$PID" || true
echo "=== END ==="
tail -n 30 "$LOG"
grep -q MARIS_DEPLOY_OK "$LOG"
