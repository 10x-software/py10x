#!/bin/bash
# Start a single-node MongoDB replica set for cloud (Claude Code on the web) sessions.
#
# Wired up as a SessionStart hook in .claude/settings.json. Runs every session
# because the cloud environment cache stores files, not running processes, so the
# container must be (re)started each time.
#
# Guarded to cloud only: CLAUDE_CODE_REMOTE is set to "true" exclusively in
# Claude Code on the web sessions. On your laptop (including Remote Control, which
# runs locally) the variable is unset and this script no-ops, leaving your local
# mongo-rs untouched.
#
# infra_10x requires a *replica set* (the storage layer uses transactions), not a
# standalone mongod -- hence --replSet rs0 + rs.initiate().
set -euo pipefail

[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0

# Already running from an earlier resume? Nothing to do.
docker ps --format '{{.Names}}' | grep -qx mongo-rs && exit 0

docker rm -f mongo-rs 2>/dev/null || true
docker run -d --name mongo-rs -p 27017:27017 mongo:8 --replSet rs0

# Wait for mongod to accept connections.
until docker exec mongo-rs mongosh --quiet --eval 'db.adminCommand("ping").ok' 2>/dev/null | grep -q 1; do
  sleep 1
done

# Initiate the single-node replica set (idempotent: ignore "already initialized").
docker exec mongo-rs mongosh --quiet --eval 'rs.initiate()' || true

# Wait until this node is the writable primary before handing control to Claude.
until docker exec mongo-rs mongosh --quiet --eval 'db.hello().isWritablePrimary' 2>/dev/null | grep -q true; do
  sleep 1
done

echo "mongo-rs ready: replica set rs0 primary on 127.0.0.1:27017"
