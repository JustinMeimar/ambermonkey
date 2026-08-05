#!/usr/bin/env bash
# Replay one tp6 recording and run a single instrumented pageload
# against it. Emits every process's JSONL on stdout.
#
#   site-replay.sh <site> <url> <mode> [outdir]
#
# <site> names a directory under $MOZPROXY_ROOT of the form
# mitm5-linux-firefox-<site>; those are unpacked by an AWSY tp6 run.
# <mode> is structural or demand.
set -uo pipefail

SITE="${1:?site}"
URL="${2:?url}"
MODE="${3:-structural}"
OUT="${4:-}"

FIREFOX=/home/justin/spidermonkey/firefox
BIN="$FIREFOX/build-browser-release/dist/bin/firefox"
MOZPROXY_ROOT="$FIREFOX/build-browser-release/_tests/awsy/html/testing/mozproxy"
MITM="$MOZPROXY_ROOT/mitmdump-5.1.1/mitmdump"
ADDON="$FIREFOX/testing/mozbase/mozproxy/mozproxy/backends/mitm/scripts/alternate-server-replay.py"
RECORDING="$MOZPROXY_ROOT/mitm5-linux-firefox-$SITE/dump.mp"
PORT="${PORT:-8081}"

for f in "$MITM" "$ADDON" "$RECORDING" "$BIN"; do
  [ -e "$f" ] || { echo "missing: $f" >&2; exit 2; }
done

WORK=$(mktemp -d "/tmp/amber-site-$SITE.XXXXXX")
[ -n "$OUT" ] || OUT="$WORK/instr"
mkdir -p "$OUT"
MITMLOG="$WORK/mitmproxy.log"

"$MITM" \
  --listen-host 127.0.0.1 --listen-port "$PORT" \
  --set upstream_cert=false \
  --set upload_dir="$WORK" \
  --set websocket=false \
  --set server_replay_files="$RECORDING" \
  --scripts "$ADDON" \
  > "$MITMLOG" 2>&1 &
MPID=$!

# mitmdump binds its listener before the replay addon finishes parsing
# the recording, so wait for the banner rather than a TCP connect.
for _ in $(seq 1 120); do
  grep -q 'listening at' "$MITMLOG" 2>/dev/null && break
  kill -0 "$MPID" 2>/dev/null || { echo "mitmdump died:" >&2; cat "$MITMLOG" >&2; exit 3; }
  sleep 1
done
grep -q 'listening at' "$MITMLOG" || { echo "mitmdump never became ready:" >&2; cat "$MITMLOG" >&2; kill "$MPID"; exit 3; }

cd "$FIREFOX"
env \
  MOZ_DISABLE_CONTENT_SANDBOX=1 \
  JS_INSTR=all \
  JS_INSTR_DIR="$OUT" \
  JS_INSTR_MODE="$MODE" \
  JS_INSTR_RUN_ID="$SITE-$MODE" \
  MOZCONFIG=/home/justin/spidermonkey/ambermonkey/mozconfigs/browser-release.mozconfig \
  ./mach browsertime --headless -n 1 -b firefox \
    --firefox.binaryPath "$BIN" \
    --proxy.http "localhost:$PORT" --proxy.https "localhost:$PORT" \
    --firefox.acceptInsecureCerts \
    --pageCompleteCheckNetworkIdle \
    --timeouts.networkIdle 3000 \
    --timeouts.pageCompleteCheck 30000 \
    "$URL" >&2
RC=$?

kill "$MPID" 2>/dev/null
wait "$MPID" 2>/dev/null

echo "site=$SITE mode=$MODE rc=$RC jsonl=$(ls "$OUT" | wc -l) dir=$OUT" >&2
cat "$OUT"/*.jsonl 2>/dev/null
exit "$RC"
