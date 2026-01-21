from core_10x.code_samples.person import Person

p = Person(first_name = 'John', last_name = 'Doe')
p.save()

ppl = Person.load_many()
