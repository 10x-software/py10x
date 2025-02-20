from core_10x.code_samples.person import Person

p = Person(first_name = 'Sasha', last_name = 'Davidovich')
assert p._rev == 0
assert p.id() == 'Sasha|Davidovich'
print(p.full_name)
print(p.serialize(False))
print(p.serialize(True))

p1 = Person(first_name='John', last_name='Doe', age=30)
assert p1.id() == 'John|Doe'