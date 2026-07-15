from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

import pytest

from core_10x.named_constant import EnumBits, NamedConstant
from core_10x.trait_definition import T
from core_10x.traitable import Traitable
from infra_10x.duckdb_store import DuckDbStore
from infra_10x.ibis_store import IbisCollection, _DATA, _ID, _REV


@pytest.fixture
def store():
    s = DuckDbStore()
    s.collection('test', {})  # blob-only: no trait metadata for column promotion
    return s


@pytest.fixture
def collection(store) -> IbisCollection:
    return store.collection('test', {})  # blob-only


def _index_names(collection: IbisCollection) -> set[str]:
    rows = collection._store._con.execute(
        f"SELECT index_name FROM duckdb_indexes() WHERE table_name = '{collection.collection_name()}'"
    ).fetchall()
    return {r[0] for r in rows}


class TestCreateIndex:
    def test_id_column_creates_index(self, collection):
        collection.create_index('idx_id', _ID)
        assert 'idx_id' in _index_names(collection)

    def test_rev_column_creates_index(self, collection):
        collection.create_index('idx_rev', _REV)
        assert 'idx_rev' in _index_names(collection)

    def test_json_field_raises(self, collection):
        with pytest.raises(ValueError, match='cannot index'):
            collection.create_index('idx_name', 'name')
        assert 'idx_name' not in _index_names(collection)

    def test_list_with_json_field_raises(self, collection):
        with pytest.raises(ValueError, match="cannot index 'name'"):
            collection.create_index('idx_mixed', [(_ID, 1), ('name', -1)])
        assert 'idx_mixed' not in _index_names(collection)

    def test_list_id_rev_only_creates_index(self, collection):
        collection.create_index('idx_id_rev', [(_ID, 1), (_REV, -1)])
        assert 'idx_id_rev' in _index_names(collection)

    def test_returns_name(self, collection):
        assert collection.create_index('idx_id', _ID) == 'idx_id'

    def test_idempotent(self, collection):
        collection.create_index('idx_rev', _REV)
        collection.create_index('idx_rev', _REV)  # IF NOT EXISTS — no error
        assert 'idx_rev' in _index_names(collection)

    def test_unique_true(self, collection):
        """Mongo Index(..., unique=True) parity on real columns."""
        collection.create_index('idx_rev_uq', _REV, unique=True)
        assert 'idx_rev_uq' in _index_names(collection)

    def test_index_expr_none_raises(self, collection, monkeypatch):
        monkeypatch.setattr(type(collection), '_index_expr', lambda self, field: None)
        with pytest.raises(ValueError, match='cannot index'):
            collection.create_index('idx_id', _ID)

    def test_index_expr_override_used_for_payload_field(self, collection, monkeypatch):
        """Dialect hook maps a payload field to a real column expression."""

        def _expr(self, field: str) -> str | None:
            if field == 'name':
                return _REV  # stand-in for e.g. Postgres (_data->>'name')
            if field in (_ID, _REV):
                return field
            return None

        monkeypatch.setattr(type(collection), '_index_expr', _expr)
        collection.create_index('idx_via_hook', 'name')
        assert 'idx_via_hook' in _index_names(collection)


class HybridNC(NamedConstant):
    FOO = ()


class HybridFlags(EnumBits):
    READ = ()


class _TraitFixtureBase(Traitable):
    test_id: str = T(T.ID)
    i: int = T()
    f: float = T()
    b: bool = T()
    s: str = T()
    dt: datetime = T()
    d: date = T()
    by: bytes = T()
    cl: type = T()
    lst: list = T()
    dct: dict = T()
    nc: HybridNC = T()


TraitFixture = type(
    f'TraitFixture#{uuid.uuid4().hex}',
    (_TraitFixtureBase,),
    {'__module__': __name__, 'custom_collection': True},
)


def _blob_keys(store: DuckDbStore, coll_name: str, doc_id: str) -> set[str]:
    safe = coll_name.replace('"', '""')
    row = store._con.execute(f'SELECT {_DATA} FROM "{safe}" WHERE {_ID} = ?', [doc_id]).fetchone()
    return set(json.loads(row[0] or '{}').keys())


def _sql_columns(store: DuckDbStore, coll_name: str) -> set[str]:
    return set(store._collection_columns(coll_name)) - {_ID, _REV, _DATA}


def _eligible_column_traits(trait_dir: dict) -> set[str]:
    """Scalar, non-runtime/reserved traits that must be stored as SQL columns."""
    from py10x_kernel import BTraitFlags

    from infra_10x.ibis_store import _SCALAR_WIRE_TYPES

    out: set[str] = set()
    for name, trait in trait_dir.items():
        if trait.flags_on(BTraitFlags.RUNTIME | BTraitFlags.RESERVED):
            continue
        st = trait.serialize_to_types()
        if isinstance(st, tuple) or st not in _SCALAR_WIRE_TYPES:
            continue
        out.add(name)
    return out


def assert_eligible_fields_are_columns(
    store: DuckDbStore, coll_name: str, trait_dir: dict, *, doc_id: str | None = None
) -> None:
    """Assert every column-eligible trait is a real SQL column (not only in JSON).

    When ``doc_id`` is given, also assert those fields are absent from that row's blob
    when present on the document (values live in columns).
    """
    eligible = _eligible_column_traits(trait_dir)
    cols = _sql_columns(store, coll_name)
    missing = eligible - cols
    assert not missing, f'eligible traits missing as SQL columns: {sorted(missing)}; have {sorted(cols)}'
    if doc_id is not None:
        blob = _blob_keys(store, coll_name, doc_id)
        leaked = eligible & blob
        assert not leaked, f'eligible traits still in _data blob: {sorted(leaked)}'


@pytest.fixture
def hybrid_store():
    store = DuckDbStore()
    coll_name = f'hybrid_{uuid.uuid4().hex}'
    coll = store.collection(coll_name, TraitFixture.s_dir)
    yield store, coll, coll_name
    store.delete_collection(coll_name)


@pytest.mark.parametrize(
    'field, sample_value, in_column',
    [
        ('i', 7, True),
        ('f', 1.25, True),
        ('b', True, True),
        ('s', 'txt', True),
        ('dt', datetime(2024, 6, 1, tzinfo=timezone.utc), True),
        ('d', date(2024, 6, 1), True),
        ('by', b'raw', True),
        ('cl', int, True),
        ('lst', [1, 2], False),
        ('dct', {'k': 1}, False),
        ('nc', HybridNC.FOO, False),
    ],
)
def test_hybrid_column_vs_blob_placement(hybrid_store, field, sample_value, in_column):
    store, coll, coll_name = hybrid_store
    doc_id = f'id_{field}'
    trait = TraitFixture.trait(field)
    wire_value = trait.serialize_value(sample_value) if field in ('cl', 'nc') else sample_value
    coll.save_new({'_id': doc_id, 'test_id': doc_id, field: wire_value})
    cols = _sql_columns(store, coll_name)
    blob = _blob_keys(store, coll_name, doc_id)
    if in_column:
        assert field in cols
        assert field not in blob
    else:
        assert field not in cols
        assert field in blob
    # Full eligibility check for traits that have been written at least once
    # (lazy ALTER only creates columns on first write of each field).
    if in_column:
        assert field in coll.col_trait_dir
        assert field in cols


def test_schema_evolution_lazy_alter(hybrid_store):
    store, coll, coll_name = hybrid_store
    assert 'i' not in _sql_columns(store, coll_name)
    coll.save_new({'_id': 'evo', 'test_id': 'evo', 'i': 99})
    assert 'i' in coll._collection_columns()


def test_blob_fallback_when_add_column_unsupported(hybrid_store, monkeypatch):
    """Without online DDL, column-eligible fields still save — in ``_data`` only."""
    store, coll, coll_name = hybrid_store
    monkeypatch.setattr(type(store), 's_supports_add_column_if_not_exists', False)
    coll.save_new({'_id': 'x', 'test_id': 'x', 'i': 1})
    assert 'i' not in _sql_columns(store, coll_name)
    assert 'i' in _blob_keys(store, coll_name, 'x')
    assert coll.load('x')['i'] == 1


def test_datetime_filter_on_empty_table_json_path():
    """``_at < watermark`` must type-check on an empty collection (no ``_at`` column yet)."""
    from core_10x.trait_filter import LT, f
    from core_10x.traitable import Traitable

    class Ev(Traitable, custom_collection=True):
        name: str = T(T.ID)
        _at: datetime = T(T.TS_TIME)

    store = DuckDbStore()
    coll_name = f'filt_{uuid.uuid4().hex}'
    coll = store.collection(coll_name, Ev.s_dir)
    assert '_at' not in coll._collection_columns() or '_at' not in _sql_columns(store, coll_name)
    assert list(coll.find(f(_at=LT(datetime.now(timezone.utc))))) == []
    store.delete_collection(coll_name)


def test_datetime_filter_on_json_blob_casts_to_timestamp(monkeypatch):
    """Blob-fallback ``_at`` (ISO string in ``_data``) must still compare to datetime."""
    from core_10x.trait_definition import T
    from core_10x.trait_filter import LT, f
    from core_10x.traitable import Traitable

    class Ev(Traitable, custom_collection=True):
        name: str = T(T.ID)
        _at: datetime = T(T.TS_TIME)

    monkeypatch.setattr(DuckDbStore, 's_supports_add_column_if_not_exists', False)
    store = DuckDbStore()
    coll_name = f'filt_blob_{uuid.uuid4().hex}'
    coll = store.collection(coll_name, Ev.s_dir)
    assert '_at' not in _sql_columns(store, coll_name)
    coll.save_new(store.add_ts('_at', T.TS_TIME, {'_id': '1', 'name': 'a'}))
    assert '_at' in _blob_keys(store, coll_name, '1')
    rows = list(coll.find(f(_at=LT(datetime(2099, 1, 1)))))
    assert len(rows) == 1
    store.delete_collection(coll_name)


def test_index_on_scalar_column_after_save(hybrid_store):
    _store, coll, _coll_name = hybrid_store
    coll.save_new({'_id': 'idx', 'test_id': 'idx', 'i': 42})
    coll.create_index('idx_i', 'i')
    assert 'idx_i' in _index_names(coll)


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
    name = f'clr_{uuid.uuid4().hex}'
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


def test_merge_trait_dir_unions_bundle_member_schemas():
    """Re-opening the same collection with another member's s_dir unions columns."""
    from core_10x.traitable import Traitable

    class MemberA(Traitable, custom_collection=True):
        name: str = T(T.ID)
        howl_pitch: int = T()

    class MemberB(Traitable, custom_collection=True):
        name: str = T(T.ID)
        den: str = T()

    store = DuckDbStore()
    coll_name = f'bundle_{uuid.uuid4().hex}'
    c_a = store.collection(coll_name, MemberA.s_dir)
    c_b = store.collection(coll_name, MemberB.s_dir)
    assert c_a is c_b
    assert 'howl_pitch' in c_b.col_trait_dir
    assert 'den' in c_b.col_trait_dir

    c_a.save_new({'_id': 'w', 'name': 'wolf', 'howl_pitch': 7})
    c_b.save_new({'_id': 'b', 'name': 'bear', 'den': 'cave'})
    cols = _sql_columns(store, coll_name)
    assert 'howl_pitch' in cols and 'den' in cols
    assert 'howl_pitch' not in _blob_keys(store, coll_name, 'w')
    assert 'den' not in _blob_keys(store, coll_name, 'b')
    store.delete_collection(coll_name)


def test_ts_fields_land_in_sql_columns_when_eligible():
    """add_ts stamps for column-eligible traits must not leave NULL SQL columns."""
    from core_10x.traitable import Traitable

    class Ev(Traitable, custom_collection=True):
        name: str = T(T.ID)
        _at: datetime = T(T.TS_TIME)
        _who: str = T(T.TS_USER)

    store = DuckDbStore()
    coll_name = f'ts_{uuid.uuid4().hex}'
    coll = store.collection(coll_name, Ev.s_dir)
    body = store.add_ts('_at', T.TS_TIME, {'_id': '1', 'name': 'a'})
    body = store.add_ts('_who', T.TS_USER, body)
    result = coll.save_new(body)
    assert '_at' in result and '_who' in result
    assert_eligible_fields_are_columns(store, coll_name, Ev.s_dir, doc_id='1')
    row = store._con.execute(
        f'SELECT "_at", "_who", {_DATA} FROM "{coll_name}" WHERE {_ID} = ?', ['1']
    ).fetchone()
    assert row[0] is not None, '_at SQL column must be non-null after add_ts'
    assert row[1] == store.auth_user()
    blob = json.loads(row[2] or '{}')
    assert '_at' not in blob and '_who' not in blob
    store.delete_collection(coll_name)

