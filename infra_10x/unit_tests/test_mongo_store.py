"""MongoDB-specific dialect tests (shared suites run via conftest ts_instance matrix)."""

from core_10x.concrete_resource import CONCRETE_RESOURCE
from core_10x.traitable import VaultResourceAccessor
from infra_10x.mongodb_store import MongoStore


def test_mongo_parse_uri_round_trip():
    uri = 'mongodb://user:pass@localhost:27017/testdb?ssl=false&serverSelectionTimeoutMS=5000'
    args = MongoStore.parse_uri(uri)

    assert args[MongoStore.HOSTNAME_TAG] == 'localhost'
    assert args[MongoStore.DBNAME_TAG] == 'testdb'
    assert args[MongoStore.USERNAME_TAG] == 'user'
    assert args[MongoStore.PASSWORD_TAG] == 'pass'
    assert args['port'] == 27017
    # Aliased options are folded to the short map key for translate_kwargs.
    assert args['sst'] == 5000
    assert 'serverSelectionTimeoutMS' not in args


def test_mongo_parse_uri_short_aliases():
    args = MongoStore.parse_uri('mongodb://localhost:27017/testdb?sst=5000&direct=true')
    assert args['sst'] == 5000
    assert args['direct'] is True
    tr = MongoStore.translate_kwargs(args)
    assert tr['serverSelectionTimeoutMS'] == 5000
    assert tr['directConnection'] is True


def test_mongo_direct_alias_uri_round_trip():
    """?direct=true must not become ?direct=True or ?directConnection=True (keyring service name)."""
    uri = 'mongodb://127.0.0.1:27017/__vault__?direct=true'
    assert MongoStore.spec_from_uri(uri).uri() == uri
    assert VaultResourceAccessor._canonical_uri(CONCRETE_RESOURCE.TS_STORE, uri) == uri


def test_mongo_string_query_param_not_json_quoted():
    """json.dumps would wrap replicaSet as %22rs0%22; keyring URIs must stay unquoted strings."""
    uri = 'mongodb://127.0.0.1:27017/db?direct=true&replicaSet=rs0'
    out = MongoStore.spec_from_uri(uri).uri()
    assert 'direct=true' in out
    assert 'replicaSet=rs0' in out
    assert '%22' not in out
    assert 'True' not in out.split('?', 1)[1]


def test_spec_from_uri_includes_protocol_tag():
    spec = MongoStore.spec_from_uri('mongodb://localhost:27017/testdb')
    assert spec.kwargs.get(MongoStore.PROTOCOL_TAG) == 'mongodb'


def test_mongo_canonical_uri_adds_default_port():
    no_port = VaultResourceAccessor._canonical_uri(CONCRETE_RESOURCE.TS_STORE, 'mongodb://vault.example.com/mydb')
    with_port = VaultResourceAccessor._canonical_uri(CONCRETE_RESOURCE.TS_STORE, 'mongodb://vault.example.com:27017/mydb')

    assert ':27017' in no_port
    assert no_port == with_port


def test_filter_and_pipeline_equivalence():
    from infra_10x.testlib.mongo_collection_helper import MongoCollectionHelperStub
    from py10x_infra import MongoCollectionHelper

    serialized_traitable = {'_id': 'AAAA', '_rev': 10, 'name': 'test', 'age': 60}

    data1 = dict(serialized_traitable)
    pipeline1: list = []
    filter1: dict = {}
    MongoCollectionHelperStub.prepare_filter_and_pipeline(data1, filter1, pipeline1)

    data2 = dict(serialized_traitable)
    pipeline2: list = []
    filter2: dict = {}
    MongoCollectionHelper.prepare_filter_and_pipeline(data2, filter2, pipeline2)

    assert filter1 == filter2
    assert pipeline1 == pipeline2
    assert data1 == data2
