from datetime import date

from infra_10x.mongodb_store import MongoStore

from core_10x.code_samples.person import Person
from core_10x.exec_control import GRAPH_ON

if __name__ == '__main__':

    with MongoStore.instance(hostname ='localhost', dbname='test', username='', password=''):
        p = Person(first_name = 'Ilya', last_name = 'Pevzner')
        p.dob = date(1971,7,1)
        p.save()
        p.dob = date(1971,7,3)
        assert p.dob== date(1971,7,3)
        with GRAPH_ON():
            assert p.dob == date(1971,7,3)  # FIX: fails here!
