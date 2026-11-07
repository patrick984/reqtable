#!/bin/sh
# Read-only health check for one verification run. Usage: doctor.sh RUN_DIR
set -eu

run_dir=$(CDPATH= cd -- "${1:?usage: doctor.sh RUN_DIR}" && pwd)
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../../.." && pwd)
. "$run_dir/server.env"
status=0
check() { if eval "$2"; then echo "ok    $1"; else echo "FAIL  $1"; status=1; fi; }

check "server pid $PID is alive" 'kill -0 "$PID" 2>/dev/null'
check "pid $PID is this run's http.server" \
    'ps -o command= -p "$PID" | grep -q "http.server $PORT --bind 127.0.0.1 --directory $run_dir/site"'
check "port $PORT is owned by pid $PID" 'lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | grep -qx "$PID"'
for page in snapshot develop diff uat-develop; do
    check "$page.html serves a report" \
        'curl -fsS "http://127.0.0.1:$PORT/$page.html" 2>/dev/null | grep -q "id=\"reqtable-data\""'
done
current=$(cat "$repo"/reqtable/*.py | shasum | cut -d' ' -f1)
check "reports match current reqtable sources (relaunch if not)" '[ "$current" = "$SOURCE_SHA" ]'
echo "URL=http://127.0.0.1:$PORT/"
exit "$status"
