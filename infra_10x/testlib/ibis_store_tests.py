"""Shared ``IbisStore`` suites, parameterized over every ibis-backed dialect (DuckDB, Postgres).

Collected via ``infra_10x/unit_tests/test_ibis_store.py`` — mirrors the
``core_10x/testlib/ts_tests.py`` + ``test_ts_stores.py`` pattern for the shared ``TsStore``
suites, but scoped to dialects that go through :class:`infra_10x.ibis_store.IbisStore`
(Mongo isn't ibis-backed and has its own indexing semantics).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
import uuid6
from core_10x.exec_control import CACHE_ONLY
from core_10x.named_constant import NamedConstant
from core_10x.testlib import test_databases
from core_10x.testlib.strict import need
from core_10x.trait_definition import T
from core_10x.trait_filter import IN, LT, NE, f
from core_10x.traitable import Traitable
from core_10x.ts_store import TsDuplicateKeyError
from core_10x.ts_store_type import TS_STORE_TYPE
from py10x_kernel import BTraitFlags

from infra_10x.duckdb_store import DuckDbStore
from infra_10x.ibis_store import _DATA, _ID, _REV, _SCALAR_WIRE_TYPES, IbisCollection, IbisStore
from infra_10x.postgres_store import PostgresStore


@pytest.fixture(params=[protocol for protocol in TS_STORE_TYPE.all_names() if issubclass(TS_STORE_TYPE.ts_store_class(protocol), IbisStore)])
def ibis_store(request, live_store) -> IbisStore:
    """One store per ibis dialect (from the registry); a backend that is down skips."""
    need(store := live_store(store_protocol := request.param), f'{store_protocol} running (ibis store tests)')
    return store


def _new_pad_collection(store: IbisStore, coll_name: str) -> IbisCollection:
    class Pad(Traitable, custom_collection=True, keep_history=False):
        pad: int = T()

    return store.collection(coll_name, Pad.s_dir)


@pytest.fixture
def collection(ibis_store) -> IbisCollection:
    coll_name = f'ibis_{uuid6.uuid7().hex}'
    coll = _new_pad_collection(ibis_store, coll_name)
    yield coll
    ibis_store.delete_collection(coll_name)


def index_exists(store: IbisStore, collection_name: str, logical_name: str) -> bool:
    """Dialect catalog lookup for whether ``create_index`` actually landed a physical index."""
    phys_idx = store._physical_index_name(collection_name, logical_name)
    if isinstance(store, PostgresStore):
        rows = store._execute('SELECT 1 FROM pg_indexes WHERE indexname = ?', [phys_idx])
    elif isinstance(store, DuckDbStore):
        rows = store._execute('SELECT 1 FROM duckdb_indexes() WHERE index_name = ?', [phys_idx])
    else:
        raise NotImplementedError(f'index_exists: no catalog lookup for {type(store).__name__}')
    return bool(rows)


def has_index(collection: IbisCollection, logical_name: str) -> bool:
    return index_exists(collection._store, collection.collection_name(), logical_name)


class TestCreateIndex:
    def test_id_column_creates_index(self, collection):
        collection.create_index('idx_id', _ID)
        assert has_index(collection, 'idx_id')

    def test_rev_column_creates_index(self, collection):
        collection.create_index('idx_rev', _REV)
        assert has_index(collection, 'idx_rev')

    def test_list_id_rev_only_creates_index(self, collection):
        collection.create_index('idx_id_rev', [(_ID, 1), (_REV, -1)])
        assert has_index(collection, 'idx_id_rev')

    def test_returns_name(self, collection):
        assert collection.create_index('idx_id', _ID) == 'idx_id'

    def test_idempotent(self, collection):
        collection.create_index('idx_rev', _REV)
        collection.create_index('idx_rev', _REV)  # IF NOT EXISTS — no error
        assert has_index(collection, 'idx_rev')

    def test_unique_true(self, collection):
        """Mongo Index(..., unique=True) parity on real columns."""
        collection.create_index('idx_rev_uq', _REV, unique=True)
        assert has_index(collection, 'idx_rev_uq')

    def test_same_logical_name_on_two_collections(self, ibis_store):
        """Index names are namespaced per-table; IF NOT EXISTS must not skip the second collection."""
        a_name, b_name = f'ibis_a_{uuid6.uuid7().hex}', f'ibis_b_{uuid6.uuid7().hex}'
        a = _new_pad_collection(ibis_store, a_name)
        b = _new_pad_collection(ibis_store, b_name)
        try:
            a.create_index('shared_idx', _REV)
            b.create_index('shared_idx', _REV)
            assert has_index(a, 'shared_idx')
            assert has_index(b, 'shared_idx')
        finally:
            ibis_store.delete_collection(a_name)
            ibis_store.delete_collection(b_name)

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
        assert has_index(collection, 'idx_via_hook')

    def test_digit_leading_collection_name_gets_alpha_prefixed_index(self, ibis_store):
        """custom_collection often uses a bare UUID hex collection name (starts with a digit)."""
        coll_name = '0' + uuid6.uuid7().hex[1:]
        assert coll_name[0].isdigit()
        coll = _new_pad_collection(ibis_store, coll_name)
        try:
            phys = ibis_store._physical_index_name(coll_name, '_at_idx')
            assert phys[0].isalpha(), phys
            assert coll.create_index('_at_idx', _REV) == '_at_idx'
            assert has_index(coll, '_at_idx')
        finally:
            ibis_store.delete_collection(coll_name)


def test_duplicate_key_raises(collection):
    collection.save_new({'_id': 'x', 'pad': 1})
    with pytest.raises(TsDuplicateKeyError):
        collection.save_new({'_id': 'x', 'pad': 2})


def test_json_structure_filter_matches_stored_blob(collection):
    """EQ/NE/IN on a JSON object or array, compared as the dialect's native JSON type.

    Postgres JSONB renormalizes on write (reorders object keys, re-spaces), so a text
    comparison against ``json.dumps`` output could never match and EQ silently returned
    nothing. ``ibis_compare_pair`` compares as JSON instead, so the dialect's own equality
    applies. Keys here are deliberately not in jsonb's canonical order.
    """
    obj = {'zz': 1, 'a': 2, 'kkk': 3}
    arr = ['builtins/int', 10, 20]
    collection.save_new({'_id': '1', 'pad': 0, 'obj': obj, 'arr': arr})
    collection.save_new({'_id': '2', 'pad': 0, 'obj': {'other': 1}, 'arr': ['x']})

    assert {r['_id'] for r in collection.find(f(obj=obj))} == {'1'}
    assert {r['_id'] for r in collection.find(f(arr=arr))} == {'1'}
    assert collection.count(f(obj=obj)) == 1
    assert {r['_id'] for r in collection.find(f(obj=NE(obj)))} == {'2'}
    assert collection.count(f(obj={'zz': 1, 'a': 999, 'kkk': 3})) == 0
    # Mixed IN list: a JSON literal round-trips scalars too, so one encoding covers both.
    assert {r['_id'] for r in collection.find(f(obj=IN([obj, 'not-a-struct'])))} == {'1'}


def test_json_structure_filter_key_order(collection):
    """Whether key order matters is the dialect's own JSON semantics, not ours.

    Postgres compares ``jsonb`` values — order-insensitive. DuckDB's JSON is text-backed, so
    reordering does not match there. Asserting both keeps the difference deliberate rather
    than accidental.
    """
    collection.save_new({'_id': '1', 'pad': 0, 'obj': {'zz': 1, 'a': 2, 'kkk': 3}})
    reordered = {'a': 2, 'kkk': 3, 'zz': 1}
    expected = 1 if isinstance(collection._store, PostgresStore) else 0
    assert collection.count(f(obj=reordered)) == expected


def test_collection_names_from_catalog(ibis_store):
    """Listing reads the catalog, and skips tables that are not collections.

    A persistent dialect shares its database with whatever else lives there, so a table
    without the ``_id`` / ``_rev`` / ``_data`` layout must not be reported as a collection
    (``copy_to`` would otherwise try to copy it).
    """
    coll_name = f'catalog_{uuid6.uuid7().hex}'
    other = f'plain_{uuid6.uuid7().hex}'
    coll = _new_pad_collection(ibis_store, coll_name)
    coll.save_new({'_id': 'a', 'pad': 1})
    ibis_store._execute(f'CREATE TABLE "{other}" (x INTEGER)')
    try:
        names = ibis_store.collection_names()
        assert coll_name in names
        assert other not in names, 'table without the collection layout must not be listed'
        assert ibis_store.collection_names(f'{coll_name}.*') == [coll_name]
    finally:
        ibis_store._execute(f'DROP TABLE "{other}"')
        ibis_store.delete_collection(coll_name)


def test_json_field_raises(collection):
    """Blob-only field indexing: DuckDB raises; Postgres can via a JSONB path (_index_expr)."""
    if isinstance(collection._store, PostgresStore):
        assert collection.create_index('idx_name', 'name') == 'idx_name'
        assert has_index(collection, 'idx_name')
    else:
        with pytest.raises(ValueError, match='cannot index'):
            collection.create_index('idx_name', 'name')
        assert not has_index(collection, 'idx_name')


def test_list_with_json_field_raises(collection):
    if isinstance(collection._store, PostgresStore):
        assert collection.create_index('idx_mixed', [(_ID, 1), ('name', -1)]) == 'idx_mixed'
        assert has_index(collection, 'idx_mixed')
    else:
        with pytest.raises(ValueError, match="cannot index 'name'"):
            collection.create_index('idx_mixed', [(_ID, 1), ('name', -1)])
        assert not has_index(collection, 'idx_mixed')


# --- hybrid column-vs-blob placement, across every trait wire type ---------------------


class HybridNC(NamedConstant):
    FOO = ()


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
    f'TraitFixture#{uuid6.uuid7().hex}',
    (_TraitFixtureBase,),
    {'__module__': __name__, 'custom_collection': True},
)


def blob_keys(store: IbisStore, coll_name: str, doc_id: str) -> set[str]:
    rows = store._execute(f'SELECT {_DATA} FROM {store._qname(coll_name)} WHERE {_ID} = ?', [doc_id])
    if not rows:
        return set()
    raw = rows[0][0]
    data = raw if isinstance(raw, dict) else json.loads(raw or '{}')
    return set(data.keys())


def sql_columns(store: IbisStore, coll_name: str) -> set[str]:
    return set(store._collection_columns(coll_name)) - {_ID, _REV, _DATA}


def _eligible_column_traits(trait_dir: dict) -> set[str]:
    """Scalar, non-runtime/reserved traits that must be stored as SQL columns."""
    out: set[str] = set()
    for name, trait in trait_dir.items():
        if trait.flags_on(BTraitFlags.RUNTIME | BTraitFlags.RESERVED):
            continue
        st = trait.serialize_to_types()
        if isinstance(st, tuple) or st not in _SCALAR_WIRE_TYPES:
            continue
        out.add(name)
    return out


def assert_eligible_fields_are_columns(store: IbisStore, coll_name: str, trait_dir: dict, *, doc_id: str | None = None) -> None:
    """Assert every column-eligible trait is a real SQL column (not only in JSON).

    When ``doc_id`` is given, also assert those fields are absent from that row's blob
    when present on the document (values live in columns).
    """
    eligible = _eligible_column_traits(trait_dir)
    cols = sql_columns(store, coll_name)
    missing = eligible - cols
    assert not missing, f'eligible traits missing as SQL columns: {sorted(missing)}; have {sorted(cols)}'
    if doc_id is not None:
        blob = blob_keys(store, coll_name, doc_id)
        leaked = eligible & blob
        assert not leaked, f'eligible traits still in _data blob: {sorted(leaked)}'


@pytest.fixture(params=[True, False], ids=['with_add_column', 'blob_only_store'])
def hybrid_store(request, ibis_store, monkeypatch):
    """Hybrid collection on the parameterized dialect; False simulates no online ADD COLUMN."""
    if not request.param:
        monkeypatch.setattr(type(ibis_store), 's_supports_add_column_if_not_exists', False)
    coll_name = f'hybrid_{uuid6.uuid7().hex}'
    coll = ibis_store.collection(coll_name, TraitFixture.s_dir)
    yield ibis_store, coll, coll_name
    ibis_store.delete_collection(coll_name)


def _want_sql_column(store: IbisStore, column_eligible: bool) -> bool:
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
    cols = sql_columns(store, coll_name)
    blob = blob_keys(store, coll_name, doc_id)
    if _want_sql_column(store, column_eligible):
        assert field in cols
        assert field not in blob
        assert field in coll.col_trait_dir
    else:
        assert field not in cols
        assert field in blob


def test_schema_evolution_lazy_alter(hybrid_store):
    store, coll, coll_name = hybrid_store
    assert 'i' not in sql_columns(store, coll_name)
    coll.save_new({'_id': 'evo', 'test_id': 'evo', 'i': 99})
    if store.s_supports_add_column_if_not_exists:
        assert 'i' in coll._collection_columns()
    else:
        assert 'i' not in coll._collection_columns()
        assert 'i' in blob_keys(store, coll_name, 'evo')
        assert coll.load('evo')['i'] == 99


def test_traitable_ref_promoted_to_sql_column(ibis_store, monkeypatch):
    """Non-embeddable Traitable refs are serialized as str and are promoted to VARCHAR columns."""

    class RefTarget(Traitable, custom_collection=True, keep_history=False):
        name: str = T(T.ID)

    class RefOwner(Traitable, custom_collection=True, keep_history=False):
        name: str = T(T.ID)
        peer: RefTarget = T(T.NOT_EMBEDDABLE)

    assert RefOwner.s_dir['peer'].serialize_to_types() is str
    assert 'peer' in _eligible_column_traits(RefOwner.s_dir)

    store = ibis_store
    coll_name = f'ref_col_{uuid6.uuid7().hex}'
    coll = store.collection(coll_name, RefOwner.s_dir)
    with CACHE_ONLY():
        target = RefTarget(name='t1', _collection_name='targets')
        wire = RefOwner.s_dir['peer'].serialize_value(target, replace_xnone=True)
    assert wire == 't1^targets'
    coll.save_new({'_id': 'o1', 'name': 'o1', 'peer': wire})

    assert 'peer' in coll.col_trait_dir
    assert 'peer' in sql_columns(store, coll_name)
    assert 'peer' not in blob_keys(store, coll_name, 'o1')
    row = store._execute(f'SELECT peer FROM {store._qname(coll_name)} WHERE {_ID} = ?', ['o1'])
    assert row[0][0] == 't1^targets'

    # Without ADD COLUMN, ref stays in the blob (still str wire).
    monkeypatch.setattr(type(store), 's_supports_add_column_if_not_exists', False)
    coll2_name = f'ref_blob_{uuid6.uuid7().hex}'
    coll2 = store.collection(coll2_name, RefOwner.s_dir)
    coll2.save_new({'_id': 'o2', 'name': 'o2', 'peer': wire})
    assert 'peer' not in sql_columns(store, coll2_name)
    assert 'peer' in blob_keys(store, coll2_name, 'o2')
    store.delete_collection(coll_name)
    store.delete_collection(coll2_name)


def test_index_on_scalar_column_after_save(hybrid_store):
    """Once promoted, a scalar column can always be indexed.

    Without ADD COLUMN: DuckDB can't index the still-blob-only field (no physical column,
    no JSON-path fallback), but Postgres can via a JSONB path expression (see
    ``_index_expr``) — so "cannot index an unpromoted field" is DuckDB-only.
    """
    store, coll, _coll_name = hybrid_store
    coll.save_new({'_id': 'idx', 'test_id': 'idx', 'i': 42})
    if store.s_supports_add_column_if_not_exists or isinstance(store, PostgresStore):
        assert coll.create_index('idx_i', 'i') == 'idx_i'
        assert has_index(coll, 'idx_i')
    else:
        with pytest.raises(ValueError, match='cannot index'):
            coll.create_index('idx_i', 'i')


@pytest.mark.parametrize('supports_add_column', [True, False], ids=['with_add_column', 'blob_only_store'])
def test_ts_fields_when_eligible(ibis_store, supports_add_column, monkeypatch):
    """add_ts stamps land in SQL columns when ADD COLUMN is on; else in ``_data``."""
    store = ibis_store
    if not supports_add_column:
        monkeypatch.setattr(type(store), 's_supports_add_column_if_not_exists', False)

    class Ev(Traitable, custom_collection=True):
        name: str = T(T.ID)
        _at: datetime = T(T.TS_TIME)
        _who: str = T(T.TS_USER)

    coll_name = f'ts_{uuid6.uuid7().hex}'
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
        row = store._execute(f'SELECT "_at", "_who", {_DATA} FROM {store._qname(coll_name)} WHERE {_ID} = ?', ['1'])[0]
        assert row[0] is not None, '_at SQL column must be non-null after add_ts'
        assert row[1] == store.auth_user()
        raw_blob = row[2]
        blob = raw_blob if isinstance(raw_blob, dict) else json.loads(raw_blob or '{}')
        assert '_at' not in blob and '_who' not in blob
    else:
        assert '_at' not in sql_columns(store, coll_name)
        blob = blob_keys(store, coll_name, '1')
        assert '_at' in blob and '_who' in blob
        doc = coll.load('1')
        assert doc['_who'] == store.auth_user()
        assert doc['_at'] is not None
    store.delete_collection(coll_name)


def test_datetime_filter_on_empty_table_json_path(ibis_store):
    """``_at < watermark`` must type-check on an empty collection (no ``_at`` column yet)."""

    class Ev(Traitable, custom_collection=True):
        name: str = T(T.ID)
        _at: datetime = T(T.TS_TIME)

    store = ibis_store
    coll_name = f'filt_{uuid6.uuid7().hex}'
    coll = store.collection(coll_name, Ev.s_dir)
    assert '_at' not in coll._collection_columns() or '_at' not in sql_columns(store, coll_name)
    assert list(coll.find(f(_at=LT(datetime.now(timezone.utc))))) == []
    store.delete_collection(coll_name)


def test_datetime_filter_on_json_blob_casts_to_timestamp(ibis_store, monkeypatch):
    """Blob-fallback ``_at`` (ISO string in ``_data``) must still compare to datetime."""

    class Ev(Traitable, custom_collection=True):
        name: str = T(T.ID)
        _at: datetime = T(T.TS_TIME)

    store = ibis_store
    monkeypatch.setattr(type(store), 's_supports_add_column_if_not_exists', False)
    coll_name = f'filt_blob_{uuid6.uuid7().hex}'
    coll = store.collection(coll_name, Ev.s_dir)
    assert '_at' not in sql_columns(store, coll_name)
    coll.save_new(store.add_ts('_at', T.TS_TIME, {'_id': '1', 'name': 'a'}))
    assert '_at' in blob_keys(store, coll_name, '1')
    rows = list(coll.find(f(_at=LT(datetime(2099, 1, 1)))))
    assert len(rows) == 1
    store.delete_collection(coll_name)
