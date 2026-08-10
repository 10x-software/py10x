#!/usr/bin/env python3
"""Wait until fin-base's coordinated first-party deps are on PyPI.

Reads the ``py10x-core`` pin from a built ``py10x-fin-base`` wheel, polls until that
core version is published, then polls for each exact ``==`` sibling pin declared on
that core (``py10x-kernel``, ``py10x-infra``, …). Same race as cxx10x pre-publish
waiting for core — fin-base smoke also needs core's forward-pinned siblings.

A release is "available" only when the JSON API lists files **and** the simple
index lists the version (pip's resolver uses the simple API; JSON can lead).

Env:
  PYPI_TIMEOUT_SEC  total wait budget (default 900)
  PYPI_POLL_SEC     sleep between polls (default 90)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from email.parser import Parser
from pathlib import Path
from zipfile import ZipFile

FIRST_PARTY_SIBLINGS = ('py10x-kernel', 'py10x-infra')
CORE = 'py10x-core'


def _wheel_requires(wheel: Path) -> list[str]:
    with ZipFile(wheel) as zf:
        names = [n for n in zf.namelist() if n.endswith('.dist-info/METADATA')]
        if not names:
            raise SystemExit(f'no METADATA in {wheel}')
        meta = Parser().parsestr(zf.read(names[0]).decode())
    return [v for k, v in meta.items() if k.lower() == 'requires-dist']


def _req_name_version(req: str) -> tuple[str, str] | None:
    """Return (name, version) for an exact ``name==version`` requirement (markers stripped)."""
    base = req.split(';', 1)[0].strip()
    m = re.fullmatch(r'([A-Za-z0-9._-]+)\s*==\s*([^\s,]+)', base)
    if not m:
        # Promote writes parenthesized form in pyproject; wheels usually normalize to ==.
        m = re.fullmatch(r'([A-Za-z0-9._-]+)\s*\(\s*==\s*([^\s)]+)\s*\)', base)
    if not m:
        return None
    return m.group(1).lower().replace('_', '-'), m.group(2)


def _core_pin_from_wheel(wheel: Path) -> str:
    for req in _wheel_requires(wheel):
        parsed = _req_name_version(req)
        if parsed and parsed[0] == CORE:
            return parsed[1]
    raise SystemExit(f'{wheel}: no exact {CORE}== pin in Requires-Dist')


def _normalize_project(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


def _pypi_release_exists(name: str, version: str) -> bool:
    """True when JSON lists files and the simple index lists this version (pip-visible)."""
    json_url = f'https://pypi.org/pypi/{name}/{version}/json'
    try:
        with urllib.request.urlopen(json_url, timeout=30) as resp:
            if resp.status != 200:
                return False
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise
    if not (data.get('urls') or []):
        return False

    # Pip resolves via the simple API; JSON can briefly lead the CDN.
    simple_url = f'https://pypi.org/simple/{_normalize_project(name)}/'
    try:
        with urllib.request.urlopen(simple_url, timeout=30) as resp:
            html = resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise
    # Filenames use underscores; accept either spelling in the listing.
    needle = f'{_normalize_project(name).replace("-", "_")}-{version}'
    alt = f'{_normalize_project(name)}-{version}'
    return needle in html or alt in html


def _pypi_requires_dist(name: str, version: str) -> list[str]:
    url = f'https://pypi.org/pypi/{name}/{version}/json'
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.load(resp)
    return list(data.get('info', {}).get('requires_dist') or [])


def _sibling_pins(core_version: str) -> list[tuple[str, str]]:
    pins: list[tuple[str, str]] = []
    for req in _pypi_requires_dist(CORE, core_version):
        parsed = _req_name_version(req)
        if parsed and parsed[0] in FIRST_PARTY_SIBLINGS:
            pins.append(parsed)
    return pins


def _wait_for(name: str, version: str, deadline: float, poll: int) -> None:
    while True:
        if _pypi_release_exists(name, version):
            print(f'{name}=={version} available on PyPI', flush=True)
            return
        if time.time() >= deadline:
            raise SystemExit(f'timed out waiting for {name}=={version} on PyPI')
        print(f'waiting for {name}=={version} ({poll}s)...', flush=True)
        time.sleep(poll)


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit(f'usage: {Path(sys.argv[0]).name} <py10x-fin-base.whl>')
    wheel = Path(argv[1])
    timeout = int(os.environ.get('PYPI_TIMEOUT_SEC', '900'))
    poll = int(os.environ.get('PYPI_POLL_SEC', '90'))
    deadline = time.time() + timeout

    core_ver = _core_pin_from_wheel(wheel)
    print(f'fin-base pins {CORE}=={core_ver}', flush=True)
    _wait_for(CORE, core_ver, deadline, poll)

    siblings = _sibling_pins(core_ver)
    if not siblings:
        print(f'warning: no == pins for {FIRST_PARTY_SIBLINGS} on {CORE}=={core_ver}', flush=True)
    for name, ver in siblings:
        _wait_for(name, ver, deadline, poll)


if __name__ == '__main__':
    main(sys.argv)
