from unittest.mock import MagicMock

import pytest
from core_10x.nucleus import Nucleus
from core_10x.testlib.test_store import TestStore as TraitableStore
from core_10x.trait_filter import GT, f
from core_10x.ts_store import TsStore
from core_10x.ts_union import TsUnion, TsUnionCollection, _OrderKey


@pytest.fixture
def union_collection():
    collection1 = MagicMock()
    collection2 = MagicMock()
    union = TsUnionCollection(collection1, collection2)
    return union, collection1, collection2


def test_empty():
    col = TsUnionCollection()
    assert col.collections == ()

    assert not col.id_exists('1')
    assert not col.exists(f(x=GT(1)))
    assert list(col.find()) == []
    assert col.max('x') is None
    assert col.min('x') is None
    assert col.count() == 0


def test_find(union_collection, args=None):
    union, collection1, collection2 = union_collection
    args = (f(x=GT(1)),) if args is None else args
    collection1.find.return_value = [{Nucleus.ID_TAG(): 2}]
    collection2.find.return_value = [{Nucleus.ID_TAG(): 1}]
    results = list(union.find(*args))
    assert results == [{Nucleus.ID_TAG(): 1}, {Nucleus.ID_TAG(): 2}]
    collection1.find.assert_called_once_with((args and args[0]) or None, _order=None, _at_most=0)
    collection2.find.assert_called_once_with((args and args[0]) or None, _order=None, _at_most=0)


def test_no_args(union_collection):
    test_find(union_collection, args=())


def test_find_empty(union_collection):
    union, collection1, collection2 = union_collection
    collection1.find.return_value = []
    collection2.find.return_value = []
    results = list(union.find())
    assert results == []


def test_save_new(union_collection):
    union, collection1, collection2 = union_collection
    serialized_traitable = {Nucleus.ID_TAG(): 1}
    union.save_new(serialized_traitable)
    collection1.save_new.assert_called_once_with(serialized_traitable, overwrite=False)
    collection2.save.assert_not_called()


def test_save(union_collection):
    union, collection1, collection2 = union_collection
    serialized_traitable = {Nucleus.ID_TAG(): 1}
    collection1.exists.return_value = False
    union.save(serialized_traitable)
    collection1.save_new.assert_called_once_with(serialized_traitable)
    collection1.save.assert_not_called()
    collection2.save_new.assert_not_called()
    collection2.save.assert_not_called()

    collection1.reset_mock()
    collection1.exists.return_value = True
    union.save(serialized_traitable)
    collection1.save_new.assert_not_called()
    collection1.save.assert_called_once_with(serialized_traitable)
    collection2.save_new.assert_not_called()
    collection2.save.assert_not_called()


def test_delete(union_collection):
    union, collection1, collection2 = union_collection
    id_value = '1'
    collection1.delete.return_value = True
    collection1.count.return_value = 0
    collection2.count.return_value = 0
    result = union.delete(id_value)
    assert result
    collection1.delete.assert_called_once_with(id_value)
    collection2.delete.assert_not_called()

    collection2.count.return_value = 1
    result = union.delete(id_value)
    assert not result
    collection2.delete.assert_not_called()


def test_create_index(union_collection):
    union, collection1, collection2 = union_collection
    name = 'index_name'
    trait_name = 'trait_name'
    union.create_index(name, trait_name)
    collection1.create_index.assert_called_once_with(name, trait_name)
    collection2.create_index.assert_not_called()


def test_max(union_collection):
    union, collection1, collection2 = union_collection
    trait_name = 'trait_name'
    collection1.max.return_value = {'trait_name': 1}
    collection2.max.return_value = {'trait_name': 2}
    result = union.max(trait_name)
    assert result == {'trait_name': 2}
    collection1.max.assert_called_once_with(trait_name, None)
    collection2.max.assert_called_once_with(trait_name, None)


def test_max_empty(union_collection):
    union, collection1, collection2 = union_collection
    trait_name = 'trait_name'
    collection1.max.return_value = None
    collection2.max.return_value = None
    result = union.max(trait_name)
    assert result is None


def test_min(union_collection):
    union, collection1, collection2 = union_collection
    trait_name = 'trait_name'
    collection1.min.return_value = {'trait_name': 1}
    collection2.min.return_value = {'trait_name': 2}
    result = union.min(trait_name)
    assert result == {'trait_name': 1}
    collection1.min.assert_called_once_with(trait_name, None)
    collection2.min.assert_called_once_with(trait_name, None)


def test_min_empty(union_collection):
    union, collection1, collection2 = union_collection
    trait_name = 'trait_name'
    collection1.min.return_value = None
    collection2.min.return_value = None
    result = union.min(trait_name)
    assert result is None


def test_multiple_sort_keys(union_collection):
    union, collection1, collection2 = union_collection
    data1 = [
        {'_id': '1', 'group': 'A', 'value': 30},
        {'_id': '2', 'group': 'A', 'value': 10},
        {'_id': '3', 'group': 'B', 'value': 10},
    ]
    data2 = [
        {'_id': '5', 'group': 'A', 'value': 40},
        {'_id': '6', 'group': 'B', 'value': 20},
        {'_id': '7', 'group': 'B', 'value': 20},
    ]
    collection1.find.return_value = data1
    collection2.find.return_value = data2

    # Test multiple sort keys
    results = list(union.find(_order={'group': 1, 'value': -1}))
    sorted_results = [
        {'_id': '5', 'group': 'A', 'value': 40},
        {'_id': '1', 'group': 'A', 'value': 30},
        {'_id': '2', 'group': 'A', 'value': 10},
        {'_id': '6', 'group': 'B', 'value': 20},
        {'_id': '7', 'group': 'B', 'value': 20},
        {'_id': '3', 'group': 'B', 'value': 10},
    ]
    assert results == sorted_results


def test_none_handling(union_collection):
    union, collection1, collection2 = union_collection
    data2 = [
        {'_id': '2', 'value': 20},
        {'_id': '4', 'value': 40},
    ]
    collection1.find.return_value = None
    collection2.find.return_value = data2

    # Test handling None results
    results = list(union.find())
    assert len(results) == 2
    assert [r['_id'] for r in results] == ['2', '4']

    # Test all collections returning None
    collection2.find.return_value = None
    results = list(union.find())
    assert len(results) == 0


def test_sorting(union_collection):
    union, collection1, collection2 = union_collection
    data1 = [
        {'_id': '1', 'value': 30},
        {'_id': '3', 'value': 10},
    ]
    data2 = [
        {'_id': '2', 'value': 40},
        {'_id': '4', 'value': 20},
    ]
    collection1.find.return_value = data1
    collection2.find.return_value = data2

    # Test default sorting by _id ascending
    results = list(union.find())
    assert len(results) == 4
    assert [r['_id'] for r in results] == ['1', '2', '3', '4']

    # Test descending sort by value with limit
    results = list(union.find(_order={'value': -1}, _at_most=2))
    assert [r['value'] for r in results] == [40, 30]

    # Test ascending sort by value with limit
    collection1.find.return_value = reversed(data1)
    collection2.find.return_value = reversed(data2)
    results = list(union.find(_order={'value': 1}, _at_most=3))
    assert len(results) == 3
    assert [r['value'] for r in results] == [10, 20, 30]


def test_sorting_dict(union_collection):
    union, collection1, collection2 = union_collection
    data1 = [
        {'_id': '1', 'dict_field': {'a': 1, 'b': 2}},
        {'_id': '3', 'dict_field': {'a': 2, 'b': 1}},
    ]
    data2 = [
        {'_id': '2', 'dict_field': {'a': 1, 'b': 3}},
        {'_id': '4', 'dict_field': {'a': 2, 'b': 2}},
    ]
    # Test ascending sort by dict field
    collection1.find.return_value = data1
    collection2.find.return_value = data2
    results = list(union.find(_order={'dict_field': 1}))
    assert len(results) == 4
    assert [r['_id'] for r in results] == ['1', '2', '3', '4']

    # Test descending sort by dict field
    collection1.find.return_value = reversed(data1)
    collection2.find.return_value = reversed(data2)
    results = list(union.find(_order={'dict_field': -1}))
    assert len(results) == 4
    assert [r['_id'] for r in results] == ['3', '1', '4', '2']


@pytest.fixture
def union_store():
    mock_store1 = MagicMock()
    mock_store2 = MagicMock()
    union_store = TsUnion(mock_store1, mock_store2)
    return union_store, mock_store1, mock_store2


def test_collection_names(union_store):
    union_store, mock_store1, mock_store2 = union_store
    mock_store1.collection_names.return_value = ['collection1']
    mock_store2.collection_names.return_value = ['collection2']
    result = union_store.collection_names()
    assert set(result) == {'collection1', 'collection2'}
    mock_store1.collection_names.assert_called_once()
    mock_store2.collection_names.assert_called_once()


def test_collection(union_store):
    union_store, mock_store1, mock_store2 = union_store
    collection_name = 'collection_name'
    mock_store1.collection.return_value = MagicMock()
    mock_store2.collection.return_value = MagicMock()
    result = union_store.collection(collection_name)
    assert isinstance(result, TsUnionCollection)
    mock_store1.collection.assert_called_once_with(collection_name)
    mock_store2.collection.assert_called_once_with(collection_name)


def test_delete_collection(union_store):
    union_store, mock_store1, mock_store2 = union_store
    collection_name = 'collection_name'
    union_store.delete_collection(collection_name)
    mock_store1.delete_collection.assert_called_once_with(collection_name)
    mock_store2.delete_collection.assert_not_called()


@pytest.fixture
def ts_union():
    assert not TsUnion.s_instances
    store_spec = dict(driver_name='TEST_DB', hostname='localhost', dbname='dbname1', username='')
    union_store = TsUnion.instance(store_spec, store_spec | dict(dbname='dbname2'))
    yield union_store
    TsUnion.s_instances.clear()


def test_new_instance(ts_union):
    assert isinstance(ts_union, TsUnion)
    assert all(isinstance(store, TraitableStore) for store in ts_union.stores)

    assert sum(1 for v in TsStore.s_instances.values() if isinstance(v, TsUnion)) == 1
    assert sum(1 for v in TsStore.s_instances.values() if isinstance(v, TraitableStore)) == 2

    assert list(TsUnion.s_instances.keys()) == [
        (('dbname', 'dbname1'), ('hostname', 'localhost'), ('username', '')),
        (('dbname', 'dbname2'), ('hostname', 'localhost'), ('username', '')),
        (
            (('dbname', 'dbname1'), ('driver_name', 'TEST_DB'), ('hostname', 'localhost'), ('username', '')),
            (('dbname', 'dbname2'), ('driver_name', 'TEST_DB'), ('hostname', 'localhost'), ('username', '')),
        ),
    ]


def test_equal_same_order():
    assert 0 == _OrderKey._dict_cmp({'a': 1, 'b': 2}, {'a': 1, 'b': 2})


def test_equal_different_order():
    assert 1 == _OrderKey._dict_cmp({'b': 1, 'a': 2}, {'a': 2, 'b': 1})
    assert -1 == _OrderKey._dict_cmp({'a': 1, 'b': 2}, {'b': 2, 'a': 1})


def test_less_key_order():
    assert -1 == _OrderKey._dict_cmp({'a': 1, 'b': 2}, {'b': 2, 'a': 1})  # 'a' < 'b'


def test_greater_key_order():
    assert 1 == _OrderKey._dict_cmp({'b': 2, 'a': 1}, {'a': 1, 'b': 2})  # 'b' > 'a'


def test_less_value():
    assert -1 == _OrderKey._dict_cmp({'a': 1, 'b': 2}, {'a': 1, 'b': 3})


def test_greater_value():
    assert 1 == _OrderKey._dict_cmp({'a': 1, 'b': 3}, {'a': 1, 'b': 2})


def test_shorter_less():
    assert -1 == _OrderKey._dict_cmp({'a': 1}, {'a': 1, 'b': 2})


def test_longer_greater():
    assert 1 == _OrderKey._dict_cmp({'a': 1, 'b': 2}, {'a': 1})


def test_nested_less():
    assert -1 == _OrderKey._dict_cmp({'a': {'x': 1}}, {'a': {'y': 2}})  # 'x' < 'y'


def test_nested_greater():
    assert 1 == _OrderKey._dict_cmp({'a': {'y': 2}}, {'a': {'x': 1}})  # 'y' > 'x'


def test_example_from_query():
    d = {'y': 20, 'x': 10}  # order: y, x
    od = {'x': 10, 'y': 25}  # order: x, y
    assert 1 == _OrderKey._dict_cmp(d, od)  # 'y' > 'x'


def test_counterexample_values_ignored_on_key_diff():
    d = {'a': 100}
    od = {'b': 1}
    assert -1 == _OrderKey._dict_cmp(d, od)  # 'a' < 'b', values ignored


def test_counterexample_early_value_diff():
    d = {'a': 1, 'c': 4}
    od = {'a': 2, 'b': 3}
    assert -1 == _OrderKey._dict_cmp(d, od)  # 1 < 2, later ignored
