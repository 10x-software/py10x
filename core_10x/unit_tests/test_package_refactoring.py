import importlib
import sys

import pytest
from core_10x.package_refactoring import CLASS_ID_DELIMITER, PackageRefactoring
from core_10x.py_class import PyClass

# ----------------------------------------------------------------------------
#   CLASS_ID_DELIMITER
# ----------------------------------------------------------------------------


def test_class_id_delimiter_is_slash():
    assert CLASS_ID_DELIMITER == '/'


# ----------------------------------------------------------------------------
#   default_class_id  (no registered packages involved)
# ----------------------------------------------------------------------------


def test_default_class_id_replaces_dots_with_slashes():
    cid = PackageRefactoring.default_class_id(PackageRefactoring)
    assert '.' not in cid
    assert '/' in cid


def test_default_class_id_expected_value():
    cid = PackageRefactoring.default_class_id(PackageRefactoring)
    expected = 'core_10x/package_refactoring/PackageRefactoring'
    assert cid == expected


def test_default_class_id_accepts_canonical_class_name_kwarg():
    cid = PackageRefactoring.default_class_id(canonical_class_name='a.b.c.D')
    assert cid == 'a/b/c/D'


def test_default_class_id_for_pyclass():
    cid = PackageRefactoring.default_class_id(PyClass)
    assert cid == 'core_10x/py_class/PyClass'


def test_default_class_id_rejects_non_class():
    with pytest.raises(AssertionError):
        PackageRefactoring.default_class_id('not_a_class')


# ----------------------------------------------------------------------------
#   find_class_id — falls back to default when no custom mapping exists
# ----------------------------------------------------------------------------


def test_find_class_id_matches_default_for_unmapped_class():
    cid = PackageRefactoring.find_class_id(PackageRefactoring)
    expected = PackageRefactoring.default_class_id(PackageRefactoring)
    assert cid == expected


def test_find_class_id_for_py_class():
    cid = PackageRefactoring.find_class_id(PyClass)
    assert cid == 'core_10x/py_class/PyClass'


# ----------------------------------------------------------------------------
#   find_class — inverse of find_class_id
# ----------------------------------------------------------------------------


def test_find_class_resolves_package_refactoring():
    cid = 'core_10x/package_refactoring/PackageRefactoring'
    cls = PackageRefactoring.find_class(cid)
    assert cls is PackageRefactoring


def test_find_class_resolves_py_class():
    cls = PackageRefactoring.find_class('core_10x/py_class/PyClass')
    assert cls is PyClass


def test_find_class_unknown_raises_os_error():
    with pytest.raises(OSError):
        PackageRefactoring.find_class('no_such_package/no_such_module/NoSuchClass')


# ----------------------------------------------------------------------------
#   round-trip: find_class_id -> find_class
# ----------------------------------------------------------------------------


def test_roundtrip_find_class_id_and_find_class():
    cid = PackageRefactoring.find_class_id(PyClass)
    cls = PackageRefactoring.find_class(cid)
    assert cls is PyClass


# ----------------------------------------------------------------------------
#   register_top_level_packages & instance construction
# ----------------------------------------------------------------------------


def test_register_top_level_packages_creates_instances():
    before = dict(PackageRefactoring.s_instances)
    try:
        PackageRefactoring.register_top_level_packages('core_10x')
        assert 'core_10x' in PackageRefactoring.s_instances
    finally:
        PackageRefactoring.s_instances.clear()
        PackageRefactoring.s_instances.update(before)


def test_register_unknown_package_raises_os_error():
    with pytest.raises(OSError):
        PackageRefactoring('_no_such_package_xyz_')


# ----------------------------------------------------------------------------
#   _find_or_create_instance
# ----------------------------------------------------------------------------


def test_find_or_create_instance_invalid_name_raises():
    with pytest.raises(ValueError):
        PackageRefactoring._find_or_create_instance('NoPackageSeparator')


# ----------------------------------------------------------------------------
#   move_class / remove_class — records persisted via _save and re-read
# ----------------------------------------------------------------------------


@pytest.fixture
def refact_pkg(tmp_path, monkeypatch):
    pkg_name = '_xx_refact_test_pkg'
    (tmp_path / pkg_name).mkdir()
    (tmp_path / pkg_name / '__init__.py').write_text('')
    monkeypatch.syspath_prepend(str(tmp_path))

    before = dict(PackageRefactoring.s_instances)
    PackageRefactoring.s_instances.clear()
    yield pkg_name
    PackageRefactoring.s_instances.clear()
    PackageRefactoring.s_instances.update(before)
    for mod in [m for m in sys.modules if m == pkg_name or m.startswith(f'{pkg_name}.')]:
        del sys.modules[mod]


def _reloaded(pkg_name: str) -> PackageRefactoring:
    sys.modules.pop(f'{pkg_name}._refactoring', None)
    importlib.invalidate_caches()
    return PackageRefactoring(pkg_name)


def test_move_class_saves_importable_records(refact_pkg):
    old_path = f'{refact_pkg}.old_mod.Foo'
    new_path = f'{refact_pkg}.new_mod.Foo'
    PackageRefactoring.move_class(old_path, new_path)

    cid = PackageRefactoring.default_class_id(canonical_class_name=old_path)
    assert _reloaded(refact_pkg).cid_to_path == {cid: new_path}


def test_remove_class_drops_record(refact_pkg):
    new_path = f'{refact_pkg}.new_mod.Foo'
    PackageRefactoring.move_class(f'{refact_pkg}.old_mod.Foo', new_path)

    PackageRefactoring.remove_class(new_path)

    pkg_refact = PackageRefactoring.s_instances[refact_pkg]
    assert pkg_refact.cid_to_path == {}
    assert pkg_refact.path_to_cid == {}
    assert _reloaded(refact_pkg).cid_to_path == {}
