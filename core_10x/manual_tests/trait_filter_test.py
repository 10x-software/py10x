from core_10x.code_samples.person import Person
from core_10x.trait_filter import BETWEEN, NE, OR, f
from core_10x.exec_control import CACHE_ONLY

if __name__ == '__main__':
    with CACHE_ONLY():
        p = Person(first_name = 'Sasha', last_name = 'Davidovich')

    r = OR(
        f(age=BETWEEN(50, 70), first_name=NE('Sasha')),
        f(age=17)
    )

    print(r.prefix_notation())
    print(r.eval(p))