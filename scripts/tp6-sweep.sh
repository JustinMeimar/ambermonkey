#!/usr/bin/env bash
# Run site-replay.sh over every tp6 site in one mode, keeping each
# site's per-process JSONL in its own directory.
#
#   tp6-sweep.sh <mode> <outroot>
set -uo pipefail

MODE="${1:?mode: structural|demand}"
ROOT="${2:?outroot}"
HERE=$(dirname "$(readlink -f "$0")")

mkdir -p "$ROOT"
: > "$ROOT/sweep.status"

while IFS=$'\t' read -r site url; do
  [ -n "$site" ] || continue
  case "$site" in \#*) continue;; esac
  out="$ROOT/$site"
  if [ -d "$out" ] && [ -n "$(ls "$out"/*.jsonl 2>/dev/null)" ]; then
    echo "$site SKIP (already present)" | tee -a "$ROOT/sweep.status"
    continue
  fi
  mkdir -p "$out"
  start=$SECONDS
  timeout 420 "$HERE/site-replay.sh" "$site" "$url" "$MODE" "$out" \
    > /dev/null 2> "$ROOT/$site.log"
  rc=$?
  n=$(cat "$out"/*.jsonl 2>/dev/null | wc -l)
  echo "$site rc=$rc secs=$((SECONDS-start)) lines=$n" | tee -a "$ROOT/sweep.status"
done < "$HERE/tp6-sites.tsv"

echo "sweep complete: $ROOT"
