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


class _Pad(Traitable, custom_collection=True, keep_history=False):
    """Minimal storable schema so the collection is writable; extra keys stay untyped/blob."""

    pad: int = T()


@pytest.fixture
def store():
    s = DuckDbStore()
    s.collection('test', _Pad.s_dir)
    return s


@pytest.fixture
def collection(store) -> IbisCollection:
    return store.collection('test', _Pad.s_dir)


def _index_names(collection: IbisCollection) -> set[str]:
    rows = collection._store._con.execute(f"SELECT index_name FROM duckdb_indexes() WHERE table_name = '{collection.collection_name()}'").fetchall()
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
        monkeypatch.setattr(type(collection._store), '_index_expr', lambda self, coll, field: None)
        with pytest.raises(ValueError, match='cannot index'):
            collection.create_index('idx_id', _ID)

    def test_index_expr_override_used_for_payload_field(self, collection, monkeypatch):
        """Dialect hook (on the store) maps a payload field to a real column expression."""

        def _expr(self, coll, field: str) -> str | None:
            if field == 'name':
                return _REV  # stand-in for e.g. Postgres (_data->>'name')
            if field in (_ID, _REV):
                return field
            return None

        monkeypatch.setattr(type(collection._store), '_index_expr', _expr)
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


def assert_eligible_fields_are_columns(store: DuckDbStore, coll_name: str, trait_dir: dict, *, doc_id: str | None = None) -> None:
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


@pytest.fixture(params=[True, False], ids=['with_add_column', 'blob_only_store'])
def hybrid_store(request, monkeypatch):
    """DuckDB hybrid collection; ``False`` simulates stores without online ADD COLUMN."""
    store = DuckDbStore()
    if not request.param:
        monkeypatch.setattr(type(store), 's_supports_add_column_if_not_exists', False)
    coll_name = f'hybrid_{uuid.uuid4().hex}'
    coll = store.collection(coll_name, TraitFixture.s_dir)
    yield store, coll, coll_name
    store.delete_collection(coll_name)


def _want_sql_column(store: DuckDbStore, column_eligible: bool) -> bool:
    return column_eligible and store.s_supports_add_column_if_not_exists


@pytest.mark.parametrize(
    'field, sample_value, column_eligible',
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
def test_hybrid_column_vs_blob_placement(hybrid_store, field, sample_value, column_eligible):
    store, coll, coll_name = hybrid_store
    doc_id = f'id_{field}'
    trait = TraitFixture.trait(field)
    # Match framework pre-store wire (serialize before the store layer).
    wire_value = trait.serialize_value(sample_value)
    coll.save_new({'_id': doc_id, 'test_id': doc_id, field: wire_value})
    cols = _sql_columns(store, coll_name)
    blob = _blob_keys(store, coll_name, doc_id)
    if _want_sql_column(store, column_eligible):
        assert field in cols
        assert field not in blob
        assert field in coll.col_trait_dir
    else:
        assert field not in cols
        assert field in blob


def test_traitable_ref_promoted_to_sql_column(monkeypatch):
    """Non-embeddable Traitable refs are serialized as str and are promoted to VARCHAR columns."""
    from core_10x.exec_control import CACHE_ONLY

    class RefTarget(Traitable, custom_collection=True, keep_history=False):
        name: str = T(T.ID)

    class RefOwner(Traitable, custom_collection=True, keep_history=False):
        name: str = T(T.ID)
        peer: RefTarget = T(T.NOT_EMBEDDABLE)

    assert RefOwner.s_dir['peer'].serialize_to_types() is str
    assert 'peer' in _eligible_column_traits(RefOwner.s_dir)

    store = DuckDbStore()
    coll_name = f'ref_col_{uuid.uuid4().hex}'
    coll = store.collection(coll_name, RefOwner.s_dir)
    with CACHE_ONLY():
        target = RefTarget(name='t1', _collection_name='targets')
        wire = RefOwner.s_dir['peer'].serialize_value(target, replace_xnone=True)
    assert wire == 't1^targets'
    coll.save_new({'_id': 'o1', 'name': 'o1', 'peer': wire})

    assert 'peer' in coll.col_trait_dir
    assert 'peer' in _sql_columns(store, coll_name)
    assert 'peer' not in _blob_keys(store, coll_name, 'o1')
    row = store._con.execute(
        f'SELECT peer FROM "{coll_name.replace(chr(34), chr(34) * 2)}" WHERE {_ID} = ?',
        ['o1'],
    ).fetchone()
    assert row[0] == 't1^targets'

    # Without ADD COLUMN, ref stays in the blob (still str wire).
    monkeypatch.setattr(type(store), 's_supports_add_column_if_not_exists', False)
    coll2_name = f'ref_blob_{uuid.uuid4().hex}'
    coll2 = store.collection(coll2_name, RefOwner.s_dir)
    coll2.save_new({'_id': 'o2', 'name': 'o2', 'peer': wire})
    assert 'peer' not in _sql_columns(store, coll2_name)
    assert 'peer' in _blob_keys(store, coll2_name, 'o2')
    store.delete_collection(coll_name)
    store.delete_collection(coll2_name)


def test_schema_evolution_lazy_alter(hybrid_store):
    store, coll, coll_name = hybrid_store
    assert 'i' not in _sql_columns(store, coll_name)
    coll.save_new({'_id': 'evo', 'test_id': 'evo', 'i': 99})
    if store.s_supports_add_column_if_not_exists:
        assert 'i' in coll._collection_columns()
    else:
        assert 'i' not in coll._collection_columns()
        assert 'i' in _blob_keys(store, coll_name, 'evo')
        assert coll.load('evo')['i'] == 99


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
    store, coll, _coll_name = hybrid_store
    coll.save_new({'_id': 'idx', 'test_id': 'idx', 'i': 42})
    if store.s_supports_add_column_if_not_exists:
        coll.create_index('idx_i', 'i')
        assert 'idx_i' in _index_names(coll)
    else:
        # No physical column to index when ADD COLUMN is unsupported.
        with pytest.raises(ValueError, match='cannot index'):
            coll.create_index('idx_i', 'i')


def test_untyped_json_path_string_extract_for_artifacts():
    """Keys without trait metadata: string unwrap so ``_cls`` equality works."""
    from core_10x.trait_filter import f

    store = DuckDbStore()
    coll_name = f'sort_{uuid.uuid4().hex}'
    coll = store.collection(coll_name, _Pad.s_dir)
    coll.save_new({'_id': 'a', 'n': 10, '_cls': 'Wolf#history'})
    coll.save_new({'_id': 'b', 'n': 2, '_cls': 'Cat#history'})
    assert {r['_id'] for r in coll.find(f(_cls='Cat#history'))} == {'b'}
    store.delete_collection(coll_name)


def test_untyped_json_multi_key_numeric_order():
    """Payload keys not in col_trait_dir: order/min/max use multi unwrap (numeric)."""
    store = DuckDbStore()
    coll_name = f'sort_mk_{uuid.uuid4().hex}'
    coll = store.collection(coll_name, _Pad.s_dir)
    coll.save_new({'_id': 'a', 'n': 10})
    coll.save_new({'_id': 'b', 'n': 2})
    assert 'n' not in coll.col_trait_dir
    assert [r['n'] for r in coll.find(_order={'n': 1})] == [2, 10]
    assert coll.min('n')['n'] == 2
    assert coll.max('n')['n'] == 10
    store.delete_collection(coll_name)


def test_empty_trait_dir_is_read_only():
    store = DuckDbStore()
    coll = store.collection(f'ro_{uuid.uuid4().hex}', None)
    with pytest.raises(RuntimeError, match='read-only'):
        coll.save_new({'_id': 'a', 'n': 1})
    with pytest.raises(RuntimeError, match='read-only'):
        coll.create_index('idx_id', _ID)


def test_typed_json_path_numeric_order(monkeypatch):
    """With col_trait_dir, blob-path int uses typed unwrap (numeric order, not JSON/text)."""
    from core_10x.traitable import Traitable

    class Num(Traitable, custom_collection=True):
        name: str = T(T.ID)
        n: int = T()

    store = DuckDbStore()
    monkeypatch.setattr(type(store), 's_supports_add_column_if_not_exists', False)
    coll_name = f'sort_json_{uuid.uuid4().hex}'
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
    coll_name = f'sort_col_{uuid.uuid4().hex}'
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

    coll_name = f'bundle_{uuid.uuid4().hex}'
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
    cols = _sql_columns(head, coll_name)
    if supports_add_column:
        assert 'howl_pitch' in cols and 'den' in cols
        assert 'howl_pitch' not in _blob_keys(head, coll_name, 'w')
        assert 'den' not in _blob_keys(head, coll_name, 'b')
    else:
        assert 'howl_pitch' not in cols and 'den' not in cols
        assert 'howl_pitch' in _blob_keys(head, coll_name, 'w')
        assert 'den' in _blob_keys(head, coll_name, 'b')
        assert coll.load('w')['howl_pitch'] == 7
        assert coll.load('b')['den'] == 'cave'
    store.delete_collection(coll_name)


@pytest.mark.parametrize('supports_add_column', [True, False], ids=['with_add_column', 'blob_only_store'])
def test_ts_fields_when_eligible(supports_add_column, monkeypatch):
    """add_ts stamps land in SQL columns when ADD COLUMN is on; else in ``_data``."""
    from core_10x.traitable import Traitable

    class Ev(Traitable, custom_collection=True):
        name: str = T(T.ID)
        _at: datetime = T(T.TS_TIME)
        _who: str = T(T.TS_USER)

    store = DuckDbStore()
    if not supports_add_column:
        monkeypatch.setattr(type(store), 's_supports_add_column_if_not_exists', False)
    coll_name = f'ts_{uuid.uuid4().hex}'
    coll = store.collection(coll_name, Ev.s_dir)
    body = store.add_ts('_at', T.TS_TIME, {'_id': '1', 'name': 'a'})
    body = store.add_ts('_who', T.TS_USER, body)

    # TS_TIME must be stamped by the SQL server clock (column expr or JSON merge), never a
    # Python server_time() round-trip — in both column and blob-fallback modes.
    server_time_calls = []
    orig_server_time = type(store).server_time
    monkeypatch.setattr(
        type(store),
        'server_time',
        lambda self: (server_time_calls.append(1), orig_server_time(self))[1],
    )
    result = coll.save_new(body)
    assert not server_time_calls, 'TS_TIME must be stamped by the SQL server clock, not Python server_time()'
    assert '_at' in result and '_who' in result
    assert result['_at'] is not None  # hydrated from the SQL stamp via RETURNING
    if supports_add_column:
        assert_eligible_fields_are_columns(store, coll_name, Ev.s_dir, doc_id='1')
        row = store._con.execute(f'SELECT "_at", "_who", {_DATA} FROM "{coll_name}" WHERE {_ID} = ?', ['1']).fetchone()
        assert row[0] is not None, '_at SQL column must be non-null after add_ts'
        assert row[1] == store.auth_user()
        blob = json.loads(row[2] or '{}')
        assert '_at' not in blob and '_who' not in blob
    else:
        assert '_at' not in _sql_columns(store, coll_name)
        blob = _blob_keys(store, coll_name, '1')
        assert '_at' in blob and '_who' in blob
        doc = coll.load('1')
        assert doc['_who'] == store.auth_user()
        assert doc['_at'] is not None
    store.delete_collection(coll_name)
