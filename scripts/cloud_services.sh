#!/bin/bash
# Start the test databases for cloud (Claude Code on the web) sessions: PostgreSQL (trust on
# 5432, password-auth on 5433) and a single-node MongoDB replica set on 27017.
#
# Wired up as a SessionStart hook in .claude/settings.json. Runs every session
# because the cloud environment cache stores files, not running processes, so the
# servers must be (re)started each time. scripts/cloud_setup.sh creates the Postgres
# clusters and pre-pulls the Mongo image.
#
# Guarded to cloud only: CLAUDE_CODE_REMOTE is set to "true" exclusively in
# Claude Code on the web sessions. On your laptop (including Remote Control, which
# runs locally) the variable is unset and this script no-ops, leaving your local
# databases untouched.
#
# infra_10x requires a *replica set* (the storage layer uses transactions), not a
# standalone mongod -- hence --replSet rs0 + rs.initiate().
set -euo pipefail

[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0

# Mirror of Docker Hub's mongo:8: anonymous Docker Hub pulls from the cloud egress get 429.
MONGO_IMAGE=mirror.gcr.io/library/mongo:8

for cluster in main auth; do
  pg_ctlcluster 16 "$cluster" status >/dev/null 2>&1 || pg_ctlcluster 16 "$cluster" start
done

# Nothing starts the Docker daemon in the cloud container.
if ! docker info >/dev/null 2>&1; then
  (dockerd >/var/log/dockerd.log 2>&1 &)
  until docker info >/dev/null 2>&1; do sleep 1; done
fi

# Already running from an earlier resume? Nothing to do.
docker ps --format '{{.Names}}' | grep -qx mongo-rs && exit 0

docker rm -f mongo-rs 2>/dev/null || true
docker run -d --name mongo-rs -p 27017:27017 "$MONGO_IMAGE" --replSet rs0

# Wait for mongod to accept connections.
until docker exec mongo-rs mongosh --quiet --eval 'db.adminCommand("ping").ok' 2>/dev/null | grep -q 1; do
  sleep 1
done

# Initiate the single-node replica set (idempotent: ignore "already initialized"). The member must
# be localhost: by default it is the container's hostname, which clients outside it cannot resolve.
docker exec mongo-rs mongosh --quiet --eval "rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'localhost:27017'}]})" || true

# Wait until this node is the writable primary before handing control to Claude.
until docker exec mongo-rs mongosh --quiet --eval 'db.hello().isWritablePrimary' 2>/dev/null | grep -q true; do
  sleep 1
done

echo "mongo-rs ready: replica set rs0 primary on 127.0.0.1:27017; postgres on 5432 (trust) and 5433 (password)"
