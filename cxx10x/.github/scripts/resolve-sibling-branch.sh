#!/usr/bin/env bash
# Pick the first branch name that exists on a remote repo, else main.
# Logs candidate resolution to stderr; stdout is the chosen branch name only.
set -euo pipefail

repo_url="${1:?repo URL required}"
shift

if [ "$#" -eq 0 ]; then
  echo "resolve-sibling-branch: no candidates supplied; defaulting to main" >&2
  echo "main"
  exit 0
fi

echo "resolve-sibling-branch: checking ${repo_url} (candidates: $*)" >&2

for branch in "$@"; do
  if [ -z "$branch" ]; then
    echo "resolve-sibling-branch: skipping empty candidate" >&2
    continue
  fi
  if git ls-remote --heads "$repo_url" "$branch" | grep -q .; then
    echo "resolve-sibling-branch: using ${branch} (found on remote)" >&2
    echo "$branch"
    exit 0
  fi
  echo "resolve-sibling-branch: ${branch} not found on remote" >&2
done

echo "resolve-sibling-branch: no candidate matched; defaulting to main" >&2
echo "main"
