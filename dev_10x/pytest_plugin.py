def pytest_ignore_collect(collection_path, config):
    """Limit collection to package unit test directories and skip virtualenv files."""
    if any('.venv' in part for part in collection_path.parts):
        return True
    if collection_path.is_dir():
        return False

    parts = collection_path.parts
    # Do not ignore tests located in a unit_tests parent directory.
    if len(parts) > 1 and parts[-2] == 'unit_tests':
        return False
    return True
