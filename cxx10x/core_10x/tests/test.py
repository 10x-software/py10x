from core_10x.code_samples.person import Person

p = Person(first_name = 'Sasha', last_name = 'Davidovich')
assert p.id() == 'Sasha|Davidovich'

p1 = Person(first_name='John', last_name='Doe', age=30)
assert p1.id() == 'John|Doe'