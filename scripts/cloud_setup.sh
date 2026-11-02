#!/bin/bash
# Cloud environment SETUP SCRIPT for Claude Code on the web.
#
# This file is NOT run automatically by the repo. Set the "Setup script" field of your cloud
# environment (claude.ai/code -> environment selector -> settings icon) to:
#
#     #!/bin/bash
#     bash /home/user/py10x/scripts/cloud_setup.sh
#
# or paste this file's body there. It runs as root, before the session starts, from the default branch's checkout. The result is
# snapshot-cached (~7 days); editing this file does not invalidate the cache - editing the
# environment's script or allowed hosts does. The script is killed after ~5 minutes and the session
# then starts from the partial result, uncached: the quick steps go first, and an async SessionStart
# hook (scripts/cloud_dev_env_hook.sh) finishes the dev env if it was cut off. A cold dev env takes
# ~3 minutes on a fast network, much longer on a slow one.
#
# The dev env is built as the non-root `ubuntu` user, who owns the checkout (tests that expect
# PermissionError cannot pass as root). The session itself still runs as root: run uv / pytest in
# the checkout through `as-dev`, e.g. `as-dev uv run pytest`.
#
# Network: "Trusted" plus blpapi.bloomberg.com under Allowed domains (blpapi is only published on
# Bloomberg's index). No browser download is needed - see the playwright step in cloud_dev_env.sh.
set -euxo pipefail

# A pasted body runs as a copy under /tmp, so its own location says nothing about the checkout.
for REPO in "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" "$PWD" /home/user/py10x; do
  [ -f "$REPO/uv.lock" ] && [ -x "$REPO/xx-build" ] && break
done
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

cd "$REPO"
PW_BROWSERS=/home/$DEV/.cache/ms-playwright
mkdir -p "/home/$DEV/.cache"
chown -R "$DEV:$DEV" "/home/$DEV/.cache"

# The dev user gets the system bundle: the session adds the proxy CA to it, while the proxy's own
# /root/.ccr/ca-bundle.crt is unreadable to the dev user and absent while the environment is built.
chown -R "$DEV:$DEV" "$REPO"
git config --global --add safe.directory "$REPO"
cat > /usr/local/bin/as-dev <<EOF
#!/bin/sh
CA=/etc/ssl/certs/ca-certificates.crt
exec runuser -u $DEV -- env HOME=/home/$DEV USER=$DEV PLAYWRIGHT_BROWSERS_PATH=$PW_BROWSERS \\
  PATH="\$(echo "\$PATH" | tr : '\n' | grep -v '^/root' | paste -sd:)" \\
  SSL_CERT_FILE="\$CA" REQUESTS_CA_BUNDLE="\$CA" CURL_CA_BUNDLE="\$CA" PIP_CERT="\$CA" \\
  GIT_SSL_CAINFO="\$CA" NODE_EXTRA_CA_CERTS="\$CA" "\$@"
EOF
chmod 755 /usr/local/bin/as-dev

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

# Pre-pull the MongoDB image so the per-session start is fast; dockerd only runs for the pull. The pull
# is network-bound and the dev env build mostly CPU-bound, so they overlap; neither is worth failing for.
(
  (dockerd >/var/log/dockerd.log 2>&1 &)
  timeout 60 bash -c 'until docker info >/dev/null 2>&1; do sleep 1; done'
  docker pull mirror.gcr.io/library/mongo:8 || true
  pkill -x dockerd
  timeout 30 bash -c 'while pgrep -x dockerd >/dev/null; do sleep 1; done'
) &
MONGO_PULL=$!
as-dev scripts/cloud_dev_env.sh
wait "$MONGO_PULL" || true
