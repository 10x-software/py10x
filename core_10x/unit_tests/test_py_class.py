import pytest

from core_10x.py_class import PyClass


# Use PyClass itself as the test subject wherever a real module-level class is needed.


# ----------------------------------------------------------------------------
#   name()
# ----------------------------------------------------------------------------

def test_name_canonical():
    assert PyClass.name(PyClass) == 'core_10x.py_class.PyClass'


def test_name_qual_name():
    assert PyClass.name(PyClass, PyClass.QUAL_NAME) == 'PyClass'


def test_name_no_name():
    assert PyClass.name(PyClass, PyClass.NO_NAME) == ''


def test_name_builtin_class():
    assert PyClass.name(int) == 'builtins.int'


def test_name_invalid_raises():
    with pytest.raises(ValueError):
        PyClass.name('not-a-class')


# ----------------------------------------------------------------------------
#   top_level_package()
# ----------------------------------------------------------------------------

def test_top_level_package_core_10x():
    assert PyClass.top_level_package(PyClass) == 'core_10x'


def test_top_level_package_builtin():
    assert PyClass.top_level_package(int) == 'builtins'


# ----------------------------------------------------------------------------
#   find_symbol()
# ----------------------------------------------------------------------------

def test_find_symbol_existing():
    result = PyClass.find_symbol('core_10x.py_class.PyClass')
    assert result is PyClass


def test_find_symbol_nonexistent_module():
    result = PyClass.find_symbol('nonexistent_package.module.SomeClass')
    assert result is None


def test_find_symbol_invalid_name_raises():
    with pytest.raises(ValueError):
        PyClass.find_symbol('NoModuleSeparator')


# ----------------------------------------------------------------------------
#   find()
# ----------------------------------------------------------------------------

def test_find_existing_class():
    result = PyClass.find('core_10x.py_class.PyClass')
    assert result is PyClass


def test_find_with_matching_parent():
    result = PyClass.find('core_10x.py_class.PyClass', object)
    assert result is PyClass


def test_find_with_non_matching_parent():
    result = PyClass.find('core_10x.py_class.PyClass', int)
    assert result is None


def test_find_nonexistent_returns_none():
    result = PyClass.find('core_10x.py_class.DoesNotExist')
    assert result is None


# ----------------------------------------------------------------------------
#   derived_from()
# ----------------------------------------------------------------------------

def test_derived_from_direct_parent():
    assert PyClass.derived_from(bool, int)


def test_derived_from_transitive():
    assert PyClass.derived_from(bool, object)


def test_derived_from_unrelated_is_false():
    assert not PyClass.derived_from(str, int)


def test_derived_from_multiple_parents_all_match():
    assert PyClass.derived_from(bool, int, object)


def test_derived_from_multiple_parents_one_missing():
    assert not PyClass.derived_from(bool, int, str)


def test_derived_from_excluded_parent():
    assert not PyClass.derived_from(bool, int, exclude_parents=(bool,))


def test_derived_from_excluded_not_in_hierarchy():
    assert PyClass.derived_from(bool, int, exclude_parents=(str,))


# ----------------------------------------------------------------------------
#   parents()
# ----------------------------------------------------------------------------

def test_parents_of_bool_contains_int():
    parents = PyClass.parents(bool)
    assert int in parents


def test_parents_of_bool_returns_tuple():
    # object itself has no parents and causes inspect.getclasstree to error;
    # use a concrete subclass instead.
    parents = PyClass.parents(bool)
    assert isinstance(parents, tuple)


# ----------------------------------------------------------------------------
#   own_attribute()
# ----------------------------------------------------------------------------

def test_own_attribute_exists():
    found, value = PyClass.own_attribute(PyClass, 'name')
    assert found
    assert value is not None


def test_own_attribute_not_present():
    found, value = PyClass.own_attribute(PyClass, '_attr_that_does_not_exist_xyz')
    assert not found
    assert value is None


def test_own_attribute_inherited_not_found():
    # '__class__' is not in PyClass.__dict__ directly
    found, _ = PyClass.own_attribute(PyClass, '__class__')
    assert not found


# ----------------------------------------------------------------------------
#   module_class_names()
# ----------------------------------------------------------------------------

def test_module_class_names_finds_pyclass():
    names = PyClass.module_class_names('core_10x', 'py_class.py')
    assert 'PyClass' in names


def test_module_class_names_nonexistent_file():
    names = PyClass.module_class_names('core_10x', 'does_not_exist.py')
    assert names == []


def test_module_class_names_nonexistent_package():
    names = PyClass.module_class_names('no_such_package', 'file.py')
    assert names == []


# ----------------------------------------------------------------------------
#   canonical_class_names() / class_names_by_module()
# ----------------------------------------------------------------------------

def test_canonical_class_names_finds_pyclass_in_core_10x():
    names = PyClass.canonical_class_names('core_10x')
    assert any('PyClass' in n for n in names)


def test_class_names_by_module_returns_dict():
    result = PyClass.class_names_by_module('core_10x')
    assert isinstance(result, dict)
    assert 'py_class' in result
    assert 'PyClass' in result['py_class']
