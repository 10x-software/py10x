"""Assert that a C++ extension module is rebuilt after one of its sources changes.

Usage (from a harness directory, in its venv):

    uv run --no-sync python ../assert_rebuilt.py <module> <source> -- <command ...>

Records the mtime of the installed extension (.so / .pyd) and its .pyi stub, touches <source>, runs
<command>, then fails unless both files were rewritten. Checking the stub too covers the post-build
stub-generation step, which must run with this venv's Python.

The module is located with ``importlib.util.find_spec`` rather than imported: on Windows a loaded
.pyd cannot be overwritten, so this process must not hold it while <command> rebuilds it.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if '--' not in argv or argv.index('--') != 2 or len(argv) < 4:
        print(__doc__, file=sys.stderr)
        return 2
    module, source, command = argv[0], Path(argv[1]), argv[3:]

    spec = importlib.util.find_spec(module)
    if spec is None or spec.origin is None:
        print(f'{module}: not found', file=sys.stderr)
        return 1
    binary = Path(spec.origin).resolve()
    targets = [binary]
    stub = binary.with_name(f'{module}.pyi')
    if stub.exists():
        targets.append(stub)
    before = {path: path.stat().st_mtime_ns for path in targets}

    os.utime(source)  # touch: mtime only, content unchanged
    subprocess.run(command, check=True)

    stale = [path for path in targets if path.stat().st_mtime_ns <= before[path]]
    for path in targets:
        print(f'{"NOT rebuilt" if path in stale else "rebuilt"}: {path}')
    if stale:
        print(f'{module}: touching {source} did not rebuild {", ".join(p.name for p in stale)}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
