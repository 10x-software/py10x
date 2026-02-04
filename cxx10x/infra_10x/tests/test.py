from py10x_infra import MongoCollectionHelper
from core_10x.traitable_id import ID
from core_10x.trait_filter import f
from core_10x.code_samples.person import Person
from infra_10x.mongodb_store import MongoStore

def test_prepare_filter_and_pipeline():
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



def test_load():
    with MongoStore.instance(hostname = 'localhost', dbname = 'test', username = '', password = ''):
        p = Person.load_many(f(first_name='Ilya'),_at_most=1)[0]
        print(p)
        print( Person.load(ID(p.id().value[:-1])) )


if __name__=='__main__':
    test_prepare_filter_and_pipeline()
    test_load()