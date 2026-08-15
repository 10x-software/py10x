#!/usr/bin/env bash
# Run pytest, wrapped under AddressSanitizer when asan=true, else plain.
#
# Shared by the core suite and the downstream fin-base tests so both run under
# the identical ASan harness: LD_PRELOAD libasan on Linux, cdb on Windows. Once
# py10x_kernel is ASan-instrumented, every extension that imports it (cxxfin
# included) must be loaded the same way, so there is only one harness.
#
# Usage: asan-pytest.sh <asan: true|false> <runner-os> <report-dir> [pytest args...]
# Preconditions: run from the repo root; on Windows+asan, CDB_PATH is set.
set -o pipefail

asan="$1"; runner_os="$2"; report_dir="$3"; shift 3

source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate

# ---- Standard release build: just run the suite. ----
# pytest.ini enables -n auto --dist loadscope (xdist); unique py10x_test_* DBs per worker.
if [ "$asan" != "true" ]; then
  python -m pytest "$@"
  exit $?
fi

# ---- AddressSanitizer run (nightly diagnostics). ----
# Force -n0: ASan + LD_PRELOAD across many worker processes is flaky and hard to attribute.
export XX_DISABLE_STACKTRACE=1 # avoid any secondary errors
mkdir -p "$report_dir"

if [ "$runner_os" != "Windows" ]; then
  # Linux: LD_PRELOAD libasan (python is uninstrumented) + system libstdc++ (so manylinux
  # wheels' C++ throws resolve __cxa_throw). ASan report -> file; -v names the aborting test.
  export LD_PRELOAD="$(gcc -print-file-name=libasan.so):$(gcc -print-file-name=libstdc++.so)"
  export ASAN_OPTIONS="detect_leaks=0:detect_odr_violation=0:alloc_dealloc_mismatch=0:halt_on_error=1:abort_on_error=0:log_path=${report_dir}/asan"
  # rio's conftest strips LD_PRELOAD around the browser spawn so Chromium runs clean. Bound
  # the run: SIGABRT drives faulthandler (enabled in conftest) to dump all thread stacks on a hang.
  # 124 == timeout.
  set +e; timeout --signal=ABRT 45m python -m pytest -n0 -v "$@"; code=$?; set -e
  [ "$code" = "124" ] && echo "::error::Linux ASan run exceeded 45m wall clock (likely subprocess deadlock)"
  for f in "${report_dir}"/asan.*; do [ -e "$f" ] && { echo "===== ASan report: $f ====="; cat "$f"; }; done
  exit "$code"
fi

# Windows: a stack overflow leaves ASan no stack to report, so wrap pytest in cdb to catch
# native faults and print a symbolized C++ stack. No minidump (needs the matching binaries).
export ASAN_OPTIONS="halt_on_error=1:abort_on_error=0:log_path=${report_dir}/asan"
export _NT_SYMBOL_PATH="$(cygpath -w "$(dirname "$(find .venv -name 'py10x_kernel*.pyd' | head -1)")")"
cdb="$(cygpath -u "$CDB_PATH")"
bash_win="$(cygpath -w "$(command -v bash)")"
rc_file="${RUNNER_TEMP}/pytest_rc"; rm -f "$rc_file"
cmds="${RUNNER_TEMP}/cdb_cmds.txt"
# Capture the faulting thread's exception + C++ stack between greppable banners. On stack
# overflow (sov) also hand it back to the app (gN) so faulthandler prints the Python stack too.
cap=".reload /f py10x_kernel*.pyd; .echo ===EXCEPTION===; .exr -1; .echo ===STACK BEGIN===; kP 400; .echo ===STACK END==="
{
  # Stay out of the way of ASan's routine first-chance exceptions - its managed exception
  # 0xe0736170, guard-page AVs while it probes memory, ordinary C++ EH. ASan installs its
  # own handlers for these and recovers; the debugger must pass them straight through (sxi),
  # or ASan's startup fault stops being handled and turns fatal every run. (A blanket
  # second-chance catch-all was tried and did exactly that - it never caught this crash,
  # which dies without a second chance, and made ASan init crash deterministically.)
  echo "sxi av"
  echo "sxi eh"
  echo "sxe -c \"${cap}; .echo ===pass to app===; sxi sov; gN\" sov"
  echo "sxe -c \"${cap}; .kill; qq\" bpe"
  echo "g"
} > "$cmds"
# cdb exits non-zero on a caught fault; guard it so `set -e` in the caller does not abort before
# we dump ASan's own report (log_path) and the exit codes below - that abort is exactly why
# earlier Windows ASan crashes produced no diagnostic at all.
set +e
"$cdb" -g -G -o -cf "$(cygpath -w "$cmds")" \
  "$bash_win" -c "cd '$(pwd)' && source .venv/Scripts/activate && python -m pytest -n0 -v $* ; echo \$? > '${rc_file}'"
cdb_rc=$?
set -e
code="$(cat "$rc_file" 2>/dev/null || true)"
# A missing rc_file means pytest never returned - the process died under the debugger (an
# ASan-init crash, a stack overflow, or bpe). Never let that fall through as success.
[ -n "$code" ] || { echo "::error::pytest did not report an exit code (process terminated under the debugger)"; code="${cdb_rc:-1}"; [ "$code" = 0 ] && code=1; }
for f in "${report_dir}"/asan.*; do [ -e "$f" ] && { echo "===== ASan report: $f ====="; cat "$f"; }; done
echo "cdb exit: ${cdb_rc}; pytest exit code: ${code}"
exit "${code}"
