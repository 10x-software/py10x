#!/usr/bin/env bash
# Container entrypoint for functional (unattended service) accounts. Runs as root, then drops
# privileges. See docs/USER_ONBOARDING_AUTH.md and core_10x/functional_account_keyring.py.
#
# VaultUser.myname() is OsUser.me.name() with no override, so identity must be real at the
# OS level before any Python runs. Renames the placeholder account, then execs the workload
# as that non-root user.
#
# Keyring is wired via PYTHON_KEYRING_BACKEND and XX_FUNCTIONAL_ACCOUNT_SECRETS_FILE --
# env vars survive `exec`; an in-process keyring.set_keyring() would not.
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

export PYTHON_KEYRING_BACKEND=core_10x.functional_account_keyring.FunctionalAccountKeyring
export XX_FUNCTIONAL_ACCOUNT_SECRETS_FILE="$XX_SECRETS_DIR/keyring.json"

exec gosu "$FUNCTIONAL_ACCOUNT_ID" "$@"
