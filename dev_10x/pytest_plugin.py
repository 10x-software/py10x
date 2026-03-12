PY10X_PACKAGE_DIRS = {'core_10x', 'dev_10x', 'infra_10x', 'ui_10x', 'xx_common'}


def _is_py10x_path(collection_path) -> bool:
    return any(part in PY10X_PACKAGE_DIRS for part in collection_path.parts)


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
