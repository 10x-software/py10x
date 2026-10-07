#!/usr/bin/env bash
# Install env for pre-publish tests (shared by CI and local harness).
#
# Required env:
#   CXX_ROOT              repo root (CI: workspace; local: tag worktree)
#   WORKFLOW_PYPROJECT    e.g. core_10x/pyproject.toml
#   RUN_DIR               venv + constraints.txt working directory
#
# Optional env:
#   PYPI_TIMEOUT_SEC      0 = no PyPI poll (default); >0 = poll step 1 until success
#   PYPI_POLL_SEC         sleep between polls (default 90)
set -euo pipefail

: "${CXX_ROOT:?CXX_ROOT required}"
: "${WORKFLOW_PYPROJECT:?WORKFLOW_PYPROJECT required}"
: "${RUN_DIR:?RUN_DIR required}"

PYPI_TIMEOUT_SEC=${PYPI_TIMEOUT_SEC:-0}
PYPI_POLL_SEC=${PYPI_POLL_SEC:-90}

unset CXX

case "$WORKFLOW_PYPROJECT" in
  *core_10x*) WORKFLOW_PKG=py10x-kernel; WORKFLOW_DIR=core_10x; SIBLING_PKG=py10x-infra; SIBLING_DIR=infra_10x ;;
  *) WORKFLOW_PKG=py10x-infra; WORKFLOW_DIR=infra_10x; SIBLING_PKG=py10x-kernel; SIBLING_DIR=core_10x ;;
esac
GROUP="${CXX_ROOT}/${WORKFLOW_PYPROJECT}:test"

retry_uv() {
  if [ "$PYPI_TIMEOUT_SEC" -le 0 ]; then
    "$@"
    return
  fi
  local deadline=$(( $(date +%s) + PYPI_TIMEOUT_SEC ))
  until "$@"; do
    if [ "$(date +%s)" -ge "$deadline" ]; then
      echo "timed out: $*" >&2
      exit 1
    fi
    echo "waiting for PyPI: $*" >&2
    sleep "$PYPI_POLL_SEC"
  done
}

forward_pin() {
  python3 -c "
from importlib.metadata import metadata
pkg = '$1'
for req in metadata('py10x-core').get_all('Requires-Dist') or []:
    base = req.split(';', 1)[0].strip()
    if base.startswith(f'{pkg}=='):
        print(base)
        break
else:
    raise SystemExit(f'no forward == pin for {pkg} on installed py10x-core')
"
}

mkdir -p "$RUN_DIR"
cd "$RUN_DIR"
uv python install 3.12
uv venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "workflow-package $WORKFLOW_PKG (test group -> py10x-core)" >&2

# 1) Coordinated core from PyPI; --refresh busts cached index between poll retries.
retry_uv uv pip install --refresh --no-deps --group "$GROUP" -e "$CXX_ROOT/$WORKFLOW_DIR" py10x-core
CORE_VER=$(python3 -c "import importlib.metadata as m; print(m.version('py10x-core'))")
echo "py10x-core==${CORE_VER} (from test group)" >&2

SIBLING_PIN=$(forward_pin "$SIBLING_PKG")
SIBLING_TAG="${SIBLING_PKG}-v${SIBLING_PIN#${SIBLING_PKG}==}"

# 2) Sibling-package at core's forward == pin via git tag (not checkout dir or PyPI).
echo "sibling-package ${SIBLING_PIN} @ ${SIBLING_TAG}" >&2
uv pip install "${SIBLING_PKG} @ git+file://${CXX_ROOT}@${SIBLING_TAG}#subdirectory=${SIBLING_DIR}"

# 3) Workflow-package editable + dev extras under the core release freeze (-c only; check ran at core publish).
curl -fsSL "https://raw.githubusercontent.com/10x-software/py10x/v${CORE_VER}/constraints.txt" -o constraints.txt
uv pip install --group "$GROUP" -e "$CXX_ROOT/$WORKFLOW_DIR" "py10x-core[dev,rio,qt,jit]" -c constraints.txt

# For callers that need post-install metadata (e.g. CI assertions).
cat > pre-publish.env <<EOF
CORE_VER=${CORE_VER}
WORKFLOW_PKG=${WORKFLOW_PKG}
EOF
