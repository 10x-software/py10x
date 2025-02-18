from infra_10x_i import MongoCollectionHelper
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

assert data == serialized_traitable
assert filter == {'_id': 'AAA', '_rev': 10}
assert pipeline == [{'$replaceRoot': {'newRoot': {'_id': 'AAA', '_rev': {'$cond': [{'$and': [{'$eq': ['$_id', {'$literal': 'AAA'}]}, {'$eq': ['$_rev', {'$literal': 10}]}, {'$eq': ['$name', {'$literal': 'test'}]}, {'$eq': ['$age', {'$literal': 60}]}]}, 10, 11]}}}}, {'$replaceWith': {'$setField': {'field': '_id', 'input': '$$ROOT', 'value': {'$literal': 'AAA'}}}}, {'$replaceWith': {'$setField': {'field': '_rev', 'input': '$$ROOT', 'value': {'$literal': 10}}}}, {'$replaceWith': {'$setField': {'field': 'name', 'input': '$$ROOT', 'value': {'$literal': 'test'}}}}, {'$replaceWith': {'$setField': {'field': 'age', 'input': '$$ROOT', 'value': {'$literal': 60}}}}]
