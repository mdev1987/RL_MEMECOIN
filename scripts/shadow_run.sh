#!/usr/bin/env bash
# Realtime shadow run under a supervisor, with a durable evidence log.
#
#   SHADOW_RUN=83 SHADOW_SECS=86400 scripts/shadow_run.sh
#
# oxmgr can only spawn a single executable path (no argv), so all run
# parameters come from the environment. The loop never executes orders.
set -euo pipefail
cd "$(dirname "$0")/.."
RUN="${SHADOW_RUN:-83}"
SECS="${SHADOW_SECS:-86400}"
LOG="data/shadow_run${RUN}.log"
echo "[shadow_run] start $(date -Is) run=${RUN} secs=${SECS} log=${LOG}" >&2
exec .venv/bin/python -u -m bot.shadow_loop --secs "$SECS" >>"$LOG" 2>&1
