from __future__ import annotations

from pathlib import Path
import importlib.metadata as md

import core_10x
from core_10x.global_cache import cache

PY10X_ROOT = Path(core_10x.__file__).resolve().parent.parent

@cache
def _owned_top_levels() -> set[str] | None:
    try:
        files = md.distribution('py10x-core').files or []
    except md.PackageNotFoundError:
        return None

    tops: set[str] = set()
    for f in files:
        p = Path(f)
        if not p.parts:
            continue
        top = p.parts[0]
        if Path(top).is_relative_to(PY10X_ROOT):
            tops.add(top)

    return tops


def pytest_ignore_collect(collection_path, config):
    """Only constrain collection for py10x package paths."""
    p = Path(collection_path).resolve()
    if not p.is_relative_to(PY10X_ROOT):
        # Returning None means "no opinion" so user package collection is unaffected.
        return None

    if any('.venv' in part for part in p.parts):
        return True

    tops = _owned_top_levels()
    rel = p.relative_to(PY10X_ROOT)
    parts = rel.parts
    if not parts:
        return False

    if tops and parts[0] not in tops:
        return True

    if rel.is_dir():
        return False

    # Do not ignore tests located in a unit_tests parent directory.
    return not(len(parts) > 1 and parts[-2] == 'unit_tests')

