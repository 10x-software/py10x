from pathlib import Path


import core_10x

PY10X_ROOT = Path(core_10x.__file__).resolve().parent.parent


def _is_py10x_path(collection_path) -> bool:
    return Path(collection_path).resolve().is_relative_to(PY10X_ROOT)


def pytest_ignore_collect(collection_path, config):
    """Only constrain collection for py10x package paths."""
    if not _is_py10x_path(collection_path):
        # Returning None means "no opinion" so user package collection is unaffected.
        return None
    if any('.venv' in part for part in collection_path.parts):
        return True
    if collection_path.is_dir():
        return False

    parts = collection_path.parts
    # Do not ignore tests located in a unit_tests parent directory.
    if len(parts) > 1 and parts[-2] == 'unit_tests':
        return False
    return True
