from core_10x.code_samples.person import Person
from core_10x.trait_filter import OR, BETWEEN, GE, NE, f

if __name__ == '__main__':
    p = Person(first_name = 'Sasha', last_name = 'Davidovich')

    r = OR(
        f(age=BETWEEN(50, 70), first_name=NE('Sasha')),
        f(age=17)
    )

    print(r.prefix_notation())
    print(r.eval(p))