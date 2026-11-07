#!/bin/sh
# Builds fixture reports from the working tree and serves them on a free localhost port.
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../../.." && pwd)
run_id=${1:-$(date +%Y%m%d-%H%M%S)-$$}
run_dir="$repo/.verify-runs/$run_id"
site="$run_dir/site"
fixtures="$(dirname -- "$0")/../fixtures"

if [ -e "$run_dir/server.env" ]; then
    echo "run $run_id already launched; use doctor.sh or pick a new run id" >&2
    exit 2
fi
mkdir -p "$site" "$run_dir/evidence"
cd "$repo"

python3 build.py >"$run_dir/build.log" 2>&1
reqtable() { python3 dist/reqtable.pyz "$@" >>"$run_dir/generate.log" 2>&1; }
cp "$fixtures/base.csv" "$site/base.csv"
reqtable "$site/base.csv" --id-column ID -o "$site/snapshot.html"
reqtable "$site/base.csv" --id-column ID --document-mode develop -o "$site/develop.html"
reqtable --old examples/requirements-old.csv --new examples/requirements-new.csv \
    --id-column ID -o "$site/diff.html"
reqtable requirements-uat.csv --id-column ID --traceability --document-mode develop \
    -o "$site/uat-develop.html"

port=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')
python3 -m http.server "$port" --bind 127.0.0.1 --directory "$site" >"$run_dir/server.log" 2>&1 &
pid=$!
fingerprint=$(cat reqtable/*.py | shasum | cut -d' ' -f1)
printf 'RUN_ID=%s\nPID=%s\nPORT=%s\nSOURCE_SHA=%s\n' "$run_id" "$pid" "$port" "$fingerprint" >"$run_dir/server.env"

i=0
until curl -fsS "http://127.0.0.1:$port/develop.html" 2>/dev/null | grep -q 'id="reqtable-data"'; do
    i=$((i + 1))
    if [ "$i" -gt 50 ]; then
        echo "server did not become ready; see $run_dir/server.log" >&2
        exit 1
    fi
    sleep 0.1
done

echo "RUN_DIR=$run_dir"
echo "URL=http://127.0.0.1:$port/"
