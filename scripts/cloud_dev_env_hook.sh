#!/bin/bash
# Async SessionStart hook (see .claude/settings.json): when the setup script was cut off before the dev
# env was complete, build it with cloud_dev_env.sh and report the outcome to Claude. Only the JSON
# reply goes to stdout; the build's output goes to the log.
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
command -v as-dev >/dev/null 2>&1 || exit 0
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
grep -qsv incomplete "$REPO/.venv/xx-build-mode" && exit 0

# A resume fires this hook again while an earlier build may still be running.
exec 9>/tmp/cloud_dev_env.lock
flock -n 9 || exit 0

LOG=/tmp/cloud_dev_env.log
if as-dev "$REPO/scripts/cloud_dev_env.sh" >"$LOG" 2>&1; then
  msg="The background dev env build finished: as-dev uv / pytest are ready."
else
  msg="The background dev env build failed (exit $?); see the end of $LOG, fix the cause and rerun as-dev scripts/cloud_dev_env.sh."
fi
jq -nc --arg msg "$msg" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $msg}}'
