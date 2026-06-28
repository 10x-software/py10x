#!/usr/bin/env bash
# Simulate pre-publish-tests locally (PYPI_TIMEOUT_SEC=0 — fails fast if core not on PyPI).
# Usage: .github/scripts/local-pre-publish-test.sh py10x-infra-v0.2.1rc14
set -euo pipefail

TAG=${1:?usage: $0 <tag>}
REPO_ROOT=$(git rev-parse --show-toplevel)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

case "$TAG" in
  py10x-kernel-v*) WORKFLOW_PYPROJECT=core_10x/pyproject.toml ;;
  py10x-infra-v*) WORKFLOW_PYPROJECT=infra_10x/pyproject.toml ;;
  *) echo "unknown tag prefix: $TAG" >&2; exit 1 ;;
esac

WORK=$(mktemp -d)
mkdir -p "$WORK/run"
cleanup() { git -C "$REPO_ROOT" worktree remove --force "$WORK/checkout" 2>/dev/null || true; rm -rf "$WORK"; }
trap cleanup EXIT

git -C "$REPO_ROOT" worktree add --detach "$WORK/checkout" "$TAG" >/dev/null
echo "=== tag=$TAG workflow-pyproject=$WORKFLOW_PYPROJECT ==="

export CXX_ROOT="$WORK/checkout"
export WORKFLOW_PYPROJECT
export RUN_DIR="$WORK/run"
export PYPI_TIMEOUT_SEC=0
bash "$SCRIPT_DIR/pre-publish-install.sh"

cd "$RUN_DIR"
source .venv/bin/activate
source pre-publish.env
echo "Installed: core=$(python3 -c 'import importlib.metadata as m; print(m.version("py10x-core"))') kernel=$(python3 -c 'import importlib.metadata as m; print(m.version("py10x-kernel"))') infra=$(python3 -c 'import importlib.metadata as m; print(m.version("py10x-infra"))')"

pytest --collect-only -q $(python3 -c "
import core_10x, dev_10x, infra_10x, ui_10x, xx_common
from pathlib import Path
print(' '.join(str(Path(m.__file__).resolve().parent) for m in (
    core_10x, infra_10x, ui_10x, xx_common, dev_10x)))
") 2>&1 | tail -5
echo "=== PASS for $TAG ==="
