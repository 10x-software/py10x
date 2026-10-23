"""Unreleased changelog points at ./xx-build, not the retired py10x-dev profile."""

from __future__ import annotations

import re
from pathlib import Path

from core_10x.testlib.strict import need

_ROOT = Path(__file__).resolve().parents[2]


def _unreleased() -> str:
    # 0.1.x still names the profile as history. Only Unreleased is current guidance.
    need((_ROOT / 'pyproject.toml').is_file(), 'py10x source checkout')
    text = (_ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    match = re.search(r'(?ms)^## \[Unreleased\]\n(.*?)(?=^## )', text)
    assert match, 'CHANGELOG.md has no Unreleased section'
    return match.group(1)


def _rebuild_next_to_set_mode(text: str) -> bool:
    """`./xx-build rebuild` is in the set-mode / show-mode list, not elsewhere in the bullet."""
    set_at = text.find('./xx-build set-mode')
    show_at = text.find('./xx-build show-mode')
    rebuild_at = text.find('./xx-build rebuild')
    if set_at < 0 or show_at < 0 or rebuild_at < 0:
        return False
    lo, hi = sorted((set_at, show_at))
    return lo < rebuild_at < hi or 0 < rebuild_at - hi <= 40


def test_unreleased_changelog_names_xx_build_not_py10x_dev():
    """py10x-dev is not the current build path, and ./xx-build rebuild sits next to set-mode."""
    unreleased = _unreleased()
    problems: list[str] = []
    if 'py10x-dev' in unreleased or 'py10x-core-dev' in unreleased:
        problems.append('Unreleased presents py10x-dev as the current way to build')
    if not _rebuild_next_to_set_mode(unreleased):
        problems.append('Unreleased does not name ./xx-build rebuild next to set-mode')
    assert not problems, '\n'.join(problems)
