from infra_10x_i import MongoCollectionHelper

if __name__ == '__main__':
    serialized_traitable = dict(
        _id = 'AAA',
        _rev = 10,
        name = 'test',
        age = 60
    )
    filter = {}
    pipeline = []
    data = dict(serialized_traitable)
    MongoCollectionHelper.prepare_filter_and_pipeline(data, filter, pipeline)

    assert data|filter == serialized_traitable
    assert filter == {'_id': 'AAA', '_rev': 10}
    assert pipeline == [{'$replaceRoot': {'newRoot': {'_id': 'AAA', '_rev': {'$cond': [{'$and': [{'$eq': ['$name', {'$literal': 'test'}]}, {'$eq': ['$age', {'$literal': 60}]}]}, 10, 11]}}}}, {'$replaceWith': {'$setField': {'field': 'name', 'input': '$$ROOT', 'value': {'$literal': 'test'}}}}, {'$replaceWith': {'$setField': {'field': 'age', 'input': '$$ROOT', 'value': {'$literal': 60}}}}]