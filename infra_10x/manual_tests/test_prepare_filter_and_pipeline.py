if __name__ == '__main__':
    from infra_10x.mongodb_store import MongoCollectionHelper, MongoStore

    store = MongoStore.instance('localhost', 'test', '', '')

    id_value = 'AAAA'
    rev = 10

    serialized_traitable = dict(_id=id_value, _rev=rev, name='test', age=60)

    coll = store.collection('test')

    data1 = dict(serialized_traitable)
    pipeline1 = []
    filter1 = {}
    coll.filter_and_pipeline('_id', '_rev', id_value, rev, data1, filter1, pipeline1)

    data2 = dict(serialized_traitable)
    pipeline2 = []
    filter2 = {}

    MongoCollectionHelper.prepare_filter_and_pipeline(data2, filter2, pipeline2)

    assert filter1 == filter2
    assert pipeline1 == pipeline2
