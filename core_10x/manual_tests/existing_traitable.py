from core_10x.code_samples.person import Person
from infra_10x.mongodb_store import MongoStore

db = MongoStore.instance(hostname = 'localhost', dbname = 'test')
db.begin_using()

ppl_stored = Person.load_many()

id_traits = ('last_name', 'first_name')
existing_id_traits = [
    { name: p.get_value(name) for name in id_traits}
    for p in ppl_stored
]

ppl_found = [ Person.existing_instance(**id_values) for id_values in existing_id_traits]

assert ppl_found == ppl_stored

p1 = Person.existing_instance(last_name = 'Smith', first_name = 'John')
assert p1

p2 = Person.existing_instance(last_name = 'Smith', first_name = 'Josh')
assert not p2
