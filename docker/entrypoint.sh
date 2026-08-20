#!/usr/bin/env bash
# Container entrypoint for functional (unattended service) accounts. Runs as root, then drops
# privileges. See docs/USER_ONBOARDING_AUTH.md and core_10x/functional_account_keyring.py for
# the vault side of this.
#
# core_10x.traitable.VaultUser.myname() reads OsUser.me.name() -- the real OS login name --
# with no override hook, so the functional account's identity has to be real at the OS level
# *before* any Python runs. This script renames the image's generic placeholder account to the
# pod's functional-account id (matching a Kubernetes container-start pattern used elsewhere),
# then execs the real workload directly as that renamed, non-root user -- the app itself never
# runs as root.
#
# The keyring side is wired via two environment variables (PYTHON_KEYRING_BACKEND,
# XX_FUNCTIONAL_ACCOUNT_SECRETS_FILE), not an eager "install" step: env vars (unlike Python
# interpreter state) survive `exec`, so `keyring` lazily picks up our backend and reads the
# mounted secrets file the first time the real workload calls keyring.get_password/set_password
# -- in whichever process that turns out to be. An eager install-then-exec approach was tried
# and does NOT work: exec() replaces the process image, discarding any previously-installed
# backend along with the rest of that process's interpreter state.
set -euo pipefail

: "${FUNCTIONAL_ACCOUNT_ID:?FUNCTIONAL_ACCOUNT_ID must be set (e.g. by the pod spec) -- not a secret, just the vault user_id for this account}"
: "${XX_SECRETS_DIR:=/var/run/secrets/xx-vault}"

readonly PLACEHOLDER_USER=appuser

if id "$FUNCTIONAL_ACCOUNT_ID" >/dev/null 2>&1; then
  : # already renamed (e.g. container restarted in place without image churn) -- nothing to do
elif id "$PLACEHOLDER_USER" >/dev/null 2>&1; then
  usermod -l "$FUNCTIONAL_ACCOUNT_ID" "$PLACEHOLDER_USER"
  usermod -d "/home/$FUNCTIONAL_ACCOUNT_ID" -m "$FUNCTIONAL_ACCOUNT_ID"
  groupmod -n "$FUNCTIONAL_ACCOUNT_ID" "$PLACEHOLDER_USER" 2>/dev/null || true  # best-effort; no matching group is fine
else
  echo "entrypoint.sh: neither '$FUNCTIONAL_ACCOUNT_ID' nor placeholder '$PLACEHOLDER_USER' exist" >&2
  exit 1
fi

export USER="$FUNCTIONAL_ACCOUNT_ID"
export LOGNAME="$FUNCTIONAL_ACCOUNT_ID"

# If Docker socket is bind-mounted (e.g. for `xx-user-init --command 'docker secret create ...'`),
# join whichever group owns it *before gosu*
if [ -S /var/run/docker.sock ]; then
  sock_gid="$(stat -c '%g' /var/run/docker.sock)"
  sock_group="$(getent group "$sock_gid" | cut -d: -f1 || true)"
  if [ -z "$sock_group" ]; then
    sock_group=docker-sock
    groupadd -g "$sock_gid" "$sock_group"
  fi
  usermod -aG "$sock_group" "$FUNCTIONAL_ACCOUNT_ID"
fi

export PYTHON_KEYRING_BACKEND=core_10x.functional_account_keyring.FunctionalAccountKeyring
export XX_FUNCTIONAL_ACCOUNT_SECRETS_FILE="$XX_SECRETS_DIR/keyring.json"

exec gosu "$FUNCTIONAL_ACCOUNT_ID" "$@"
