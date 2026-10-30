#!/bin/bash
# Cloud environment SETUP SCRIPT for Claude Code on the web.
#
# This file is NOT run automatically by the repo. Set the "Setup script" field of your cloud
# environment (claude.ai/code -> environment selector -> settings icon) to:
#
#     #!/bin/bash
#     bash /home/user/py10x/scripts/cloud_setup.sh
#
# It runs as root, before the session starts, from the default branch's checkout. The result is
# snapshot-cached (~7 days) only when it finishes within ~5 minutes; editing this file does not
# invalidate the cache - editing the environment's script or allowed hosts does.
#
# The dev env is built as the non-root `ubuntu` user, who owns the checkout (tests that expect
# PermissionError cannot pass as root). The session itself still runs as root: run uv / pytest in
# the checkout through `as-dev`, e.g. `as-dev uv run pytest`.
#
# Network: "Trusted" plus blpapi.bloomberg.com under Allowed domains (blpapi is only published on
# Bloomberg's index). No browser download is needed - see the playwright step below.
set -euxo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DEV=ubuntu
id -u "$DEV" >/dev/null 2>&1 || useradd -m "$DEV"

# A C++ compiler, if the image lacks one.
if ! command -v c++ >/dev/null 2>&1; then
  apt-get update
  apt-get install -y --no-install-recommends build-essential
fi

# Latest uv, system-wide: the image's uv is older than pyproject's [tool.uv] required-version.
pip install --quiet --upgrade uv
ln -sf /usr/local/bin/uv /root/.local/bin/uv
ln -sf /usr/local/bin/uvx /root/.local/bin/uvx

# The build hook runs `playwright install chromium` for the locked playwright. Satisfy it from a
# dev-owned browsers dir (install takes a lock there) whose entries for the locked revisions link
# to the image's pre-installed browsers, so nothing is downloaded.
cd "$REPO"
PW_BROWSERS=/home/$DEV/.cache/ms-playwright
PW_VERSION=$(awk '$0 == "name = \"playwright\"" { getline; gsub(/"/, "", $3); print $3 }' uv.lock)
mkdir -p "$PW_BROWSERS"
PLAYWRIGHT_BROWSERS_PATH=$PW_BROWSERS uvx --from "playwright==$PW_VERSION" playwright install --dry-run chromium |
  awk '/Install location:/ { print $3 }' |
  while read -r want; do
    name=$(basename "$want")
    have=/opt/pw-browsers/$name
    [ -d "$have" ] || have=$(find /opt/pw-browsers -maxdepth 1 -type d -name "${name%-*}-*" | sort -t- -k2 -n | tail -1)
    ln -sfn "$have" "$want"
  done
chown -R "$DEV:$DEV" "/home/$DEV/.cache"

# The proxy CA sits under /root (0700), so `as-dev` hands the dev user a readable copy, refreshed
# on every call since the proxy can rotate it.
chown -R "$DEV:$DEV" "$REPO"
git config --global --add safe.directory "$REPO"
cat > /usr/local/bin/as-dev <<EOF
#!/bin/sh
CA=/usr/local/share/ccr-ca.crt
install -m 644 /root/.ccr/ca-bundle.crt "\$CA"
exec runuser -u $DEV -- env HOME=/home/$DEV USER=$DEV PLAYWRIGHT_BROWSERS_PATH=$PW_BROWSERS \\
  PATH="\$(echo "\$PATH" | tr : '\n' | grep -v '^/root' | paste -sd:)" \\
  SSL_CERT_FILE="\$CA" REQUESTS_CA_BUNDLE="\$CA" CURL_CA_BUNDLE="\$CA" PIP_CERT="\$CA" \\
  GIT_SSL_CAINFO="\$CA" NODE_EXTRA_CA_CERTS="\$CA" "\$@"
EOF
chmod 755 /usr/local/bin/as-dev

# The dev environment (see dev_10x/README.md): build mode dev, so C++ edits rebuild on the next import.
as-dev ./xx-build init

# Test databases, started per session by scripts/cloud_services.sh. Postgres follows CI's
# .github/actions/setup-postgres: trust on 5432 with SUPERUSER roles for the OS users, and a
# password-auth cluster on 5433 with dev_10x/postgres_local.py's default password.
command -v pg_ctlcluster >/dev/null 2>&1 || apt-get install -y --no-install-recommends postgresql
# Explicit locale: without LANG the cluster defaults to SQL_ASCII, which the driver sends text as bytea to.
pg_lsclusters -h | grep -q '^16 auth ' || pg_createcluster --locale C.UTF-8 16 auth -p 5433
cat > /etc/postgresql/16/main/pg_hba.conf <<'EOF'
local all all trust
host  all all 127.0.0.1/32 trust
host  all all ::1/128      trust
EOF
cat > /etc/postgresql/16/auth/pg_hba.conf <<'EOF'
local all postgres peer
host  all all 127.0.0.1/32 scram-sha-256
host  all all ::1/128      scram-sha-256
EOF
for cluster in main auth; do
  pg_ctlcluster 16 "$cluster" stop 2>/dev/null || true
  pg_ctlcluster 16 "$cluster" start
done
for role in "$DEV" root; do
  runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname = '$role'" | grep -q 1 ||
    runuser -u postgres -- psql -qc "CREATE ROLE $role SUPERUSER LOGIN"
done
runuser -u postgres -- psql -p 5433 -qc "ALTER ROLE postgres PASSWORD 'py10x_pg_auth'"
pg_ctlcluster 16 main stop
pg_ctlcluster 16 auth stop

# Pre-pull the MongoDB image so the per-session start is fast; dockerd only runs for the pull.
(dockerd >/var/log/dockerd.log 2>&1 &)
timeout 60 bash -c 'until docker info >/dev/null 2>&1; do sleep 1; done'
docker pull mirror.gcr.io/library/mongo:8 || true
pkill -x dockerd
timeout 30 bash -c 'while pgrep -x dockerd >/dev/null; do sleep 1; done'
