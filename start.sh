#!/bin/sh
set -eu

provider_pid=""
app_pid=""

cleanup() {
    if [ -n "$provider_pid" ]; then
        kill "$provider_pid" 2>/dev/null || true
    fi
}

trap cleanup INT TERM EXIT

BGUTIL_SERVER_HOME="${BGUTIL_SERVER_HOME:-/opt/bgutil-ytdlp-pot-provider/server}"

if [ -d "$BGUTIL_SERVER_HOME/node_modules" ]; then
    (
        cd "$BGUTIL_SERVER_HOME/node_modules"
        deno run --allow-env --allow-net --allow-ffi=. --allow-read=. ../src/main.ts
    ) &
    provider_pid="$!"
else
    echo "Warning: BgUtils POT provider server not found at $BGUTIL_SERVER_HOME" >&2
fi

python main.py &
app_pid="$!"
wait "$app_pid"
