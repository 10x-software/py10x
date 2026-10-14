"""Tests for `dev_10x.xx_ci` (kernel-free CI helpers)."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from dev_10x import xx_ci
from dev_10x.xx_helpers import GitHelpers, PyPIHelpers

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(shutil.which('git') is None, reason='git not available')

KERNEL = 'py10x-kernel'
INFRA = 'py10x-infra'


def _fixture_tree(tmp_path: Path, *, kernel_pin: str) -> Path:
    """One repo: core at the root, both siblings in-tree under cxx10x/."""
    repo = tmp_path / 'py10x'
    for sub in ('cxx10x/core_10x', 'cxx10x/infra_10x'):
        (repo / sub).mkdir(parents=True)
        (repo / sub / 'pyproject.toml').write_text('[project]\nname = "x"\n', encoding='utf-8')
    (repo / 'pyproject.toml').write_text(
        '[project]\n'
        'name = "py10x-core"\n'
        f'dependencies = ["{KERNEL} ({kernel_pin})", "{INFRA} (>=0)"]\n\n'
        '[tool.dev_10x.siblings]\n'
        f'{KERNEL} = {{ path = "cxx10x/core_10x" }}\n'
        f'{INFRA} = {{ path = "cxx10x/infra_10x" }}\n',
        encoding='utf-8',
    )
    GitHelpers.git(repo, 'init', '-q', '-b', 'main')
    GitHelpers.git(repo, 'config', 'user.email', 'test@example.com')
    GitHelpers.git(repo, 'config', 'user.name', 'Test')
    GitHelpers.git(repo, 'add', '.')
    GitHelpers.git(repo, 'commit', '-qm', 'init')
    return repo


def test_latest_tag_matches_pin_in_tree(tmp_path):
    repo = _fixture_tree(tmp_path, kernel_pin='==0.0.1rc2')
    for tag in (f'{KERNEL}-v0.0.1rc1', f'{KERNEL}-v0.0.1rc2', f'{KERNEL}-v0.0.1rc3.dev', 'v0.0.1rc5'):
        GitHelpers.git(repo, 'tag', tag)
    assert xx_ci.latest_tag(repo, KERNEL) == f'{KERNEL}-v0.0.1rc2'


def test_latest_tag_rejects_unpinned_spec(tmp_path):
    repo = _fixture_tree(tmp_path, kernel_pin='==0.0.2')
    GitHelpers.git(repo, 'tag', f'{KERNEL}-v0.0.1')
    with pytest.raises(SystemExit, match='no py10x-kernel tag matches'):
        xx_ci.latest_tag(repo, KERNEL)


def _release_pyproject(tmp_path: Path, kernel_spec: str) -> Path:
    (tmp_path / 'pyproject.toml').write_text(
        '[project]\n'
        'name = "py10x-core"\n'
        f'dependencies = ["{KERNEL} ({kernel_spec})", "{INFRA} (==0.9.0)", "numpy>=2"]\n\n'
        '[tool.dev_10x.siblings]\n'
        f'{KERNEL} = {{ path = "cxx10x/core_10x" }}\n'
        f'{INFRA} = {{ path = "cxx10x/infra_10x" }}\n',
        encoding='utf-8',
    )
    return tmp_path


def test_wait_sibling_releases_waits_for_each_exact_pin(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(PyPIHelpers, 'wait_for_release', lambda name, version, deadline, poll: seen.append((name, version)) or True)
    assert xx_ci.wait_sibling_releases(_release_pyproject(tmp_path, '==1.4.1rc2')) == 0
    assert sorted(seen) == [(INFRA, '0.9.0'), (KERNEL, '1.4.1rc2')]


def test_wait_sibling_releases_fails_when_a_sibling_never_lands(tmp_path, monkeypatch):
    monkeypatch.setattr(PyPIHelpers, 'wait_for_release', lambda name, version, deadline, poll: name != KERNEL)
    assert xx_ci.wait_sibling_releases(_release_pyproject(tmp_path, '==1.4.1rc2')) == 1


def test_wait_sibling_releases_rejects_a_non_release_commit(tmp_path):
    """A `main` checkout has rc-window pins, not `==`: nothing coordinated to wait for."""
    pyproject = _release_pyproject(tmp_path, '>=1.4.1rc2,<1.4.1rc3')
    (pyproject / 'pyproject.toml').write_text(
        (pyproject / 'pyproject.toml').read_text(encoding='utf-8').replace('(==0.9.0)', '(>=0.9.0)'), encoding='utf-8'
    )
    with pytest.raises(SystemExit, match='not a release commit'):
        xx_ci.wait_sibling_releases(pyproject)
