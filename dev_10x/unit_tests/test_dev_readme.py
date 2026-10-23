"""The dev README's workflow steps match the live GitHub workflows.

`uv-sync` exits 2, and `.github/scripts/wait_finbase_pypi_deps.py` is gone; a reader who follows
the old steps cannot refresh the freeze or find the fin-base PyPI wait.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _readme() -> str:
    path = Path(__file__).resolve().parents[2] / 'dev_10x' / 'README.md'
    if not path.is_file():
        pytest.skip('dev_10x/README.md not present (installed-package test run)')
    return path.read_text(encoding='utf-8')


def _section(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin : text.index(end, begin)]


def test_refresh_constraints_uses_xx_build_not_uv_sync():
    """refresh-constraints installs with the workflow's `./xx-build init`, not retired `uv-sync`."""
    section = _section(_readme(), '### `refresh-constraints.yml`', '\n## ')
    assert './xx-build init --mode ci-release --no-group test --no-group test-extras' in section
    assert 'uv-sync' not in section


def test_finbase_smoke_polls_via_xx_ci():
    """The fin-base smoke step is `xx_ci wait_pypi_release_for_wheel`, not the deleted script."""
    section = _section(_readme(), '### py10x `finbase_wheel.yml`', '\n### ')
    assert 'xx_ci wait_pypi_release_for_wheel' in section
    assert 'wait_finbase_pypi_deps.py' not in section
