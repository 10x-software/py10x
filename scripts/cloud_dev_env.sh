#!/bin/bash
# Build the cloud dev environment, as the dev user: `as-dev scripts/cloud_dev_env.sh`. Called by
# cloud_setup.sh, and by cloud_dev_env_hook.sh when the setup script was cut off before finishing it.
# A no-op once .venv is fully synced; an interrupted venv is rebuilt from scratch.
set -euxo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
: "${PLAYWRIGHT_BROWSERS_PATH:?run through as-dev}"

grep -qsv incomplete .venv/xx-build-mode && exit 0

# The build hook runs `playwright install chromium` for the locked playwright. Satisfy it from a
# dev-owned browsers dir (install takes a lock there) whose entries for the locked revisions link
# to the image's pre-installed browsers, so nothing is downloaded. Run as the dev user so the
# playwright wheel this fetches is reused from uv's cache by the sync below.
PW_VERSION=$(awk '$0 == "name = \"playwright\"" { getline; gsub(/"/, "", $3); print $3 }' uv.lock)
mkdir -p "$PLAYWRIGHT_BROWSERS_PATH"
uvx --from "playwright==$PW_VERSION" playwright install --dry-run chromium |
  awk '/Install location:/ { print $3 }' |
  while read -r want; do
    name=$(basename "$want")
    have=/opt/pw-browsers/$name
    [ -d "$have" ] || have=$(find /opt/pw-browsers -maxdepth 1 -type d -name "${name%-*}-*" | sort -t- -k2 -n | tail -1)
    ln -sfn "$have" "$want"
  done

# Build mode dev (see dev_10x/README.md), so C++ edits rebuild on the next import.
./xx-build init --clean
