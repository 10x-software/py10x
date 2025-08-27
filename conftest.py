def pytest_ignore_collect(collection_path, config):
    if any('.venv' in part for part in collection_path.parts):
        return True
    if collection_path.is_dir():
        return False
    parts = collection_path.parts
    # Return False (i.e., do NOT ignore) if the parent directory is "unit_tests"
    if len(parts) > 1 and parts[-2] == "unit_tests":
        return False
    return True
