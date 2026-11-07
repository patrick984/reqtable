#!/bin/sh
# Stops the server this run started and removes its fixtures. Evidence is kept.
set -eu

run_dir=$(CDPATH= cd -- "${1:?usage: cleanup.sh RUN_DIR}" && pwd)
. "$run_dir/server.env"
if kill -0 "$PID" 2>/dev/null &&
    ps -o command= -p "$PID" | grep -q "http.server $PORT --bind 127.0.0.1 --directory $run_dir/site"; then
    kill "$PID"
    echo "stopped server pid $PID"
else
    echo "server pid $PID already gone or not ours; nothing killed"
fi
rm -rf "$run_dir/site"
rm -f "$run_dir/server.env"
echo "evidence kept in $run_dir/evidence"
ls "$run_dir/evidence"
