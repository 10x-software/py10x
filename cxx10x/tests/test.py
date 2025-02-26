import gc

from core_10x.code_samples.person import Person
from core_10x.exec_control import GRAPH_ON, GRAPH_OFF
from infra_10x.mongodb_store import MongoStore

#db = MongoStore.instance(hostname='localhost', dbname='test')
#with db:
    #print(db.collection_names())
    #Person.collection().delete('Sasha|Davidovich')
with GRAPH_ON():
    p = Person(first_name='Sasha', last_name='Davidovich')
    # p.age=30
    # assert p.first_name == 'Sasha'
    # assert p.full_name == 'Sasha Davidovich'
    # assert not p.older_than(50)
    p.age=55
    assert p.older_than(50)
    p.age=30
    assert not p.older_than(50)
    with GRAPH_OFF():
        assert not p.older_than(50)
        #TODO: below fails..
        # p.age=55
        # assert p.older_than(50)






