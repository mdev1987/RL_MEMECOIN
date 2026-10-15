#!/usr/bin/env bash
# Weekly forward-validation refresh: download two replay hours for a date.
# Usage: scripts/fetch_day.sh 2026-10-12 [11 [12]]
# Then add the files to REPLAY_PATHS in oxfile.toml and `oxmgr apply`.
set -euo pipefail
DATE="${1:?YYYY-MM-DD}"; H1="${2:-11}"; H2="${3:-12}"
YMD="${DATE//-/\/}"
for H in "$H1" "$H2"; do
  OUT="data/$(echo "$DATE" | tr -d '-')_${H}.jsonl.zst"
  if [ -s "$OUT" ]; then echo "exists: $OUT"; continue; fi
  echo "fetching $YMD/$H -> $OUT"
  curl -L --retry 3 -o "$OUT" "https://replay.pumpapi.io/${YMD}/${H}.jsonl.zst"
  ls -lh "$OUT"
done
