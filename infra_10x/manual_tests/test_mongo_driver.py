import uuid

from infra_10x_i import MongoDbDriver

if __name__ == '__main__':
    client = MongoDbDriver.client('localhost')

    collection = MongoDbDriver.collection(client, 'test', '10x')
    # TODO: have to keep client reference live, otherwise save_via_update_one throws..
    # del client
    
    print(collection.name())

    try:
        MongoDbDriver.save_via_update_one(collection, {'x': 1})
        assert False, 'must throw'
    except ValueError as ex:
        print(ex)

    print(MongoDbDriver.save_via_update_one(collection, {'_id': uuid.uuid1().hex, '_rev': 0, 'x': 1}))
