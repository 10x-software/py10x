import gc

from core_10x.code_samples.person import Person
from core_10x import BCache
from infra_10x.mongodb_store import MongoStore

db = MongoStore.instance(hostname='localhost', dbname='test')
with db:
    #print(db.collection_names())
    #Person.collection().delete('Sasha|Davidovich')
    p = Person(first_name='Sasha', last_name='Davidovich')
    assert p.first_name == 'Sasha'

