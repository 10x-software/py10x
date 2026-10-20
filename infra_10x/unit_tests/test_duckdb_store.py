from __future__ import annotations

import pytest
import uuid6
from core_10x.trait_definition import RT, T
from core_10x.traitable import Traitable
from infra_10x.duckdb_store import DuckDbStore
from infra_10x.ibis_store import _ID
from infra_10x.testlib.ibis_store_tests import blob_keys, sql_columns


class _Pad(Traitable, custom_collection=True, keep_history=False):
    """Minimal storable schema so the collection is writable; extra keys stay untyped/blob."""

    pad: int = T()


def test_untyped_json_path_string_extract_for_artifacts():
    """Keys without trait metadata: string unwrap so ``_cls`` equality works."""
    from core_10x.trait_filter import f

    store = DuckDbStore()
    coll_name = f'sort_{uuid6.uuid7().hex}'
    coll = store.collection(coll_name, _Pad.s_dir)
    coll.save_new({'_id': 'a', 'n': 10, '_cls': 'Wolf#history'})
    coll.save_new({'_id': 'b', 'n': 2, '_cls': 'Cat#history'})
    assert {r['_id'] for r in coll.find(f(_cls='Cat#history'))} == {'b'}
    store.delete_collection(coll_name)


def test_untyped_json_multi_key_numeric_order():
    """Payload keys not in col_trait_dir: order/min/max use multi unwrap (numeric)."""
    store = DuckDbStore()
    coll_name = f'sort_mk_{uuid6.uuid7().hex}'
    coll = store.collection(coll_name, _Pad.s_dir)
    coll.save_new({'_id': 'a', 'n': 10})
    coll.save_new({'_id': 'b', 'n': 2})
    assert 'n' not in coll.col_trait_dir
    assert [r['n'] for r in coll.find(_order={'n': 1})] == [2, 10]
    assert coll.min('n')['n'] == 2
    assert coll.max('n')['n'] == 10
    store.delete_collection(coll_name)


def test_traitable_writable_collection_prepares_columns():
    """``Class.collection(create_if_needed=True)`` creates the table and stored columns, skipping RUNTIME."""

    class Num(Traitable, custom_collection=True, keep_history=False):
        name: str = T(T.ID)
        n: int = T()
        tmp: str = RT('')

    store = DuckDbStore()
    coll_name = f'prep_{uuid6.uuid7().hex}'
    with store:
        Num.collection(coll_name)
        assert not store._collection_columns(coll_name)
        Num.collection(coll_name, create_if_needed=True)
        cols = store._collection_columns(coll_name)
        assert 'n' in cols and 'name' in cols
        assert 'tmp' not in cols
        store.delete_collection(coll_name)


def test_no_trait_dir_is_read_only():
    """``None`` = no schema declared."""
    store = DuckDbStore()
    coll = store.collection(f'ro_{uuid6.uuid7().hex}', None)
    with pytest.raises(RuntimeError, match='read-only'):
        coll.save_new({'_id': 'a', 'n': 1})
    with pytest.raises(RuntimeError, match='read-only'):
        coll.create_index('idx_id', _ID)


def test_empty_trait_dir_is_writable_blob_only():
    """``{}`` = schema declared with nothing column-eligible — writable, everything in the blob.

    Distinct from ``None`` above; ``intrinsic_trait_dir()`` returns ``{}`` for such a table,
    so ``copy_to`` depends on the two not being conflated.
    """
    store = DuckDbStore()
    name = f'blob_{uuid6.uuid7().hex}'
    coll = store.collection(name, {})
    coll.save_new({'_id': 'a', 'n': 1})
    assert coll.load('a')['n'] == 1
    assert sql_columns(store, name) == set()
    assert blob_keys(store, name, 'a') == {'n'}
    store.delete_collection(name)


def test_reopening_read_only_collection_with_empty_dir_makes_it_writable():
    """A handle first opened ``None`` is promoted when reopened with a declared schema."""
    store = DuckDbStore()
    name = f'promote_{uuid6.uuid7().hex}'
    assert store.collection(name, None)._writable is False
    assert store.collection(name, {})._writable is True
    store.delete_collection(name)


def test_typed_json_path_numeric_order(monkeypatch):
    """With col_trait_dir, blob-path int uses typed unwrap (numeric order, not JSON/text)."""
    from core_10x.traitable import Traitable

    class Num(Traitable, custom_collection=True):
        name: str = T(T.ID)
        n: int = T()

    store = DuckDbStore()
    monkeypatch.setattr(type(store), 's_supports_add_column_if_not_exists', False)
    coll_name = f'sort_json_{uuid6.uuid7().hex}'
    coll = store.collection(coll_name, Num.s_dir)
    coll.save_new({'_id': 'a', 'name': 'a', 'n': 10})
    coll.save_new({'_id': 'b', 'name': 'b', 'n': 2})
    assert 'n' not in coll._collection_columns()
    assert coll.min('n')['n'] == 2
    assert coll.max('n')['n'] == 10
    assert [r['n'] for r in coll.find(_order={'n': 1})] == [2, 10]
    store.delete_collection(coll_name)


def test_physical_column_sort_is_typed(monkeypatch):
    """Promoted SQL columns use native typed order."""
    from core_10x.traitable import Traitable

    class Num(Traitable, custom_collection=True):
        name: str = T(T.ID)
        n: int = T()

    store = DuckDbStore()
    monkeypatch.setattr(type(store), 's_supports_add_column_if_not_exists', True)
    coll_name = f'sort_col_{uuid6.uuid7().hex}'
    coll = store.collection(coll_name, Num.s_dir)
    coll.save_new({'_id': 'a', 'name': 'a', 'n': 10})
    coll.save_new({'_id': 'b', 'name': 'b', 'n': 2})
    assert 'n' in coll._collection_columns()
    assert [r['n'] for r in coll.find(_order={'n': 1})] == [2, 10]
    store.delete_collection(coll_name)


def test_column_cache_is_per_store_instance():
    """Two DuckDbStore instances must not share schema evolution cache."""
    from core_10x.traitable import Traitable

    class A(Traitable, custom_collection=True):
        name: str = T(T.ID)
        age: int = T()

    s1, s2 = DuckDbStore(), DuckDbStore()
    c1 = s1.collection('shared', A.s_dir)
    c2 = s2.collection('shared', A.s_dir)
    c1.save_new({'_id': 'x', 'name': 'n', 'age': 1})
    assert 'age' in c1._collection_columns()
    assert 'age' not in c2._collection_columns() or 'age' not in s2._collection_columns('shared')
    # s2 must ALTER its own table, not trust s1's collection cache
    c2.save_new({'_id': 'y', 'name': 'm', 'age': 2})
    assert c2.load('y')['age'] == 2


def test_column_cache_is_per_collection_instance():
    from core_10x.traitable import Traitable

    class A(Traitable, custom_collection=True):
        name: str = T(T.ID)
        age: int = T()

    store = DuckDbStore()
    name = f'clr_{uuid6.uuid7().hex}'
    coll = store.collection(name, A.s_dir)
    coll.save_new({'_id': '1', 'name': 'n', 'age': 3})
    assert 'age' in coll._collection_columns()
    store.delete_collection(name)
    # Recreate: new collection must not carry prior in-memory column set
    coll2 = store.collection(name, A.s_dir)
    assert 'age' not in coll2._collection_columns() or 'age' not in store._collection_columns(name)
    coll2.save_new({'_id': '2', 'name': 'm', 'age': 4})
    assert coll2.load('2')['age'] == 4
    store.delete_collection(name)


@pytest.mark.parametrize('store_kind', ['duckdb', 'union_head_duckdb'], ids=['duckdb', 'union_head_duckdb'])
@pytest.mark.parametrize('supports_add_column', [True, False], ids=['with_add_column', 'blob_only_store'])
def test_extend_trait_dir_unions_and_promotes(store_kind, supports_add_column, monkeypatch):
    """``extend_trait_dir`` grows the writable schema; write promotes SQL columns when enabled.

    Bundle members call ``coll.extend_trait_dir(member.s_dir)`` after opening the base.
    Also runs with ``TsUnion(DuckDb, …)`` so head-only extend still drives hybrid writes.
    """
    from core_10x.traitable import Traitable
    from core_10x.ts_union import TsUnion, TsUnionCollection

    class MemberA(Traitable, custom_collection=True):
        name: str = T(T.ID)
        howl_pitch: int = T()

    class MemberB(Traitable, custom_collection=True):
        name: str = T(T.ID)
        den: str = T()

    head = DuckDbStore()
    store = TsUnion(head, DuckDbStore()) if store_kind == 'union_head_duckdb' else head
    if not supports_add_column:
        monkeypatch.setattr(DuckDbStore, 's_supports_add_column_if_not_exists', False)

    coll_name = f'bundle_{uuid6.uuid7().hex}'
    coll = store.collection(coll_name, MemberA.s_dir)
    head_coll = coll.collections[0] if isinstance(coll, TsUnionCollection) else coll
    assert 'howl_pitch' in head_coll.col_trait_dir
    assert 'den' not in head_coll.col_trait_dir

    coll.extend_trait_dir(MemberB.s_dir)
    assert 'howl_pitch' in head_coll.col_trait_dir and 'den' in head_coll.col_trait_dir

    # Re-open applies trait_dir via extend; duckdb reuses the handle, union wraps the same head.
    coll2 = store.collection(coll_name, MemberB.s_dir)
    if store_kind == 'duckdb':
        assert coll2 is coll
    else:
        assert coll2.collections[0] is head_coll
        assert 'den' in coll2.collections[0].col_trait_dir

    coll.save_new({'_id': 'w', 'name': 'wolf', 'howl_pitch': 7})
    coll.save_new({'_id': 'b', 'name': 'bear', 'den': 'cave'})
    cols = sql_columns(head, coll_name)
    if supports_add_column:
        assert 'howl_pitch' in cols and 'den' in cols
        assert 'howl_pitch' not in blob_keys(head, coll_name, 'w')
        assert 'den' not in blob_keys(head, coll_name, 'b')
    else:
        assert 'howl_pitch' not in cols and 'den' not in cols
        assert 'howl_pitch' in blob_keys(head, coll_name, 'w')
        assert 'den' in blob_keys(head, coll_name, 'b')
        assert coll.load('w')['howl_pitch'] == 7
        assert coll.load('b')['den'] == 'cave'
    store.delete_collection(coll_name)
