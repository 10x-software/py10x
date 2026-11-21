"""Windows ASan lane: copy the MSVC ASan runtime next to every .pyd in .venv (and into Scripts/).

Python 3.8+ resolves an extension's dependent DLLs only from the system, exe and .pyd dirs, never PATH.
The runtime must come from the toolset that linked the .pyds - the pin in cxx10x/cmake/versions.cmake -
not the image default in VCToolsInstallDir: MSVC ASan DLLs don't match across toolset versions (14.52's
fails a 14.44 build's import with c0000139). On windows-2025 (VS 2026) the pinned v143 toolset is a
side-by-side component, so it is looked up in every VS install, not just VCINSTALLDIR.

Before copying, checks with dumpbin that the DLL exports every name the .pyds import from it and that the
VCRUNTIME140*.dll the process already has loaded (python's own) exports every name the DLL imports, so a
mismatch fails here, by name, instead of as "The specified procedure could not be found" under cdb.

Usage (repo root, MSVC dev env from setup-windows-build): .venv/Scripts/python .github/scripts/stage-asan-runtime.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DLL  = 'clang_rt.asan_dynamic-x86_64.dll'
ROOT = Path(__file__).resolve().parents[2]
VENV = ROOT / '.venv'


def fail(msg: str):
    print(f'::error::{msg}')
    sys.exit(1)


def pinned_toolset() -> str:
    m = re.search(r'^set\(PY10X_REQUIRED_MSVC_VERSION (\d{4})\)', (ROOT / 'cxx10x/cmake/versions.cmake').read_text(), re.MULTILINE)
    if not m:
        fail('PY10X_REQUIRED_MSVC_VERSION not found in cxx10x/cmake/versions.cmake')
    return f'14.{m[1][2:]}'  # MSVC_VERSION 19xx ships as toolset 14.xx


def toolset_dirs() -> list[Path]:
    """Every VC/Tools/MSVC/<version> dir across all VS installs (pathlib globs case-insensitively on Windows)."""
    vswhere = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    out     = subprocess.run([str(vswhere), '-all', '-products', '*', '-property', 'installationPath'], capture_output = True, text = True, check = True)
    return sorted(d for vs in out.stdout.splitlines() if vs.strip() for d in (Path(vs.strip()) / 'VC/Tools/MSVC').glob('*') if d.is_dir())


def dumpbin(flag: str, path: Path) -> list[str]:
    return subprocess.run(['dumpbin', '/nologo', flag, str(path)], capture_output = True, text = True, check = True).stdout.splitlines()


def exports(path: Path) -> set[str]:
    lines = dumpbin('/exports', path)
    start = next((i for i, line in enumerate(lines) if line.split() == ['ordinal', 'hint', 'RVA', 'name']), len(lines))
    # `ordinal hint [RVA] name [(forwarded to ...)]`, until the Summary
    names = set()
    for line in lines[start + 1:]:
        if line.strip() == 'Summary':
            break
        if m := re.match(r'\s+\d+\s+[0-9A-F]+\s+(?:[0-9A-F]{8}\s+)?(\S+)', line):
            names.add(m[1])
    return names


def imports(path: Path) -> dict[str, set[str]]:
    """{dll name (lowercase): names imported from it}; load-time imports only (delay-load ones fail lazily)."""
    by_dll, cur = {}, None
    for line in dumpbin('/imports', path):
        if 'delay load imports' in line or line.strip() == 'Summary':
            break
        if m := re.fullmatch(r'    (\S+\.dll)', line, re.IGNORECASE):
            cur = by_dll.setdefault(m[1].lower(), set())
        elif cur is not None and (m := re.fullmatch(r'\s+[0-9A-F]+ (\S+)', line)):
            cur.add(m[1])
    return by_dll


def loaded_copy(name: str) -> Path | None:
    """The copy of `name` the loader binds to: python.exe's dir first (it ships VCRUNTIME140*), then System32."""
    for d in (Path(sys.base_prefix), Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32'):
        if (d / name).is_file():
            return d / name
    return None


def main():
    toolset = pinned_toolset()
    dirs    = toolset_dirs()
    found   = [f for d in dirs if d.name.startswith(f'{toolset}.') for f in d.glob(f'bin/Hostx64/x64/{DLL}')]
    if not found:
        print(f'MSVC toolsets found: {[str(d) for d in dirs]}')
        for d in dirs:
            print(f'  {d.name}: bin={[str(f.relative_to(d)) for f in d.glob(f"bin/*/*/{DLL}")]} lib={[str(f.relative_to(d)) for f in d.glob("lib/x64/clang_rt.asan*.lib")]}')
        fail(f'{DLL} for the pinned MSVC {toolset} toolset not found in any VS install')
    asan = found[-1]
    print(f'ASan runtime: {asan}')

    # byte scan first: dumpbin over every third-party .pyd in the venv is slow
    pyds = [p for p in VENV.rglob('*.pyd') if DLL.encode() in p.read_bytes() and DLL in imports(p)]
    if not pyds:
        fail(f'no .pyd under {VENV} imports {DLL} - is the build ASan-instrumented?')
    provided = exports(asan)
    if not provided:
        fail(f'no exports parsed from `dumpbin /exports {asan}`')
    problems = [f'{p.name} imports {sorted(missing)} that {asan} does not export' for p in pyds if (missing := imports(p)[DLL] - provided)]
    for dep, names in imports(asan).items():
        if dep.startswith('vcruntime140') and (copy := loaded_copy(dep)) and (missing := names - exports(copy)):
            problems.append(f'{DLL} imports {sorted(missing)} that the {copy} python loads does not export')
    if problems:
        fail('ASan runtime would not load: ' + '; '.join(problems))

    for d in sorted({VENV / 'Scripts', *(p.parent for p in VENV.rglob('*.pyd'))}):
        shutil.copy2(asan, d / DLL)
    print(f'staged next to: {[str(p.relative_to(ROOT)) for p in pyds]}')


if __name__ == '__main__':
    main()
