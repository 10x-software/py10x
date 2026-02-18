from core_10x.testlib.ts_tests import TestTSStore, ts_setup # collected by pytest
from core_10x.testlib.ts_store_transaction_tests import TestTsStoreTransaction # collected by pytest
from infra_10x.mongodb_store import MongoCollection, MongoStore


def test_mongo_parse_uri_round_trip():
    uri = 'mongodb://user:pass@localhost:27017/testdb?ssl=false&serverSelectionTimeoutMS=5000'
    args = MongoStore.parse_uri(uri)

    assert args[MongoStore.HOSTNAME_TAG] == 'localhost'
    assert args[MongoStore.DBNAME_TAG] == 'testdb'
    assert args[MongoStore.USERNAME_TAG] == 'user'
    assert args[MongoStore.PASSWORD_TAG] == 'pass'
    assert args['port'] == 27017
    # Options are driver-dependent; we only require that custom options are propagated.
    assert 'serverSelectionTimeoutMS' in args


def test_filter_and_pipeline_equivalence():
    from py10x_infra import MongoCollectionHelper
    from infra_10x.testlib.mongo_collection_helper import MongoCollectionHelperStub

    serialized_traitable = dict(_id='AAAA', _rev=10, name='test', age=60)

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
