import gc
import sys
import uuid

from core_10x.traitable import Traitable, T, RC, RC_TRUE, trait_value

class Person(Traitable):
    first_name: str     = T(T.ID)
    last_name: str      = T(T.ID)

    age: int            = T(1)
    full_name: str      = T(T.EXPENSIVE)

    older_than: bool    = T()

    def full_name_get(self) -> str:
        return f'{self.first_name} {self.last_name}'

    def full_name_set(self, trait, value: str) -> RC:
        parts = value.split(' ')
        if(len(parts) != 2):
            return RC(False, f'"{value}" - must be "first_name last_name"')

        self.first_name = parts[0]
        self.last_name = parts[1]
        return RC_TRUE

    def older_than_get(self, age: int) -> bool:
        return self.age > age

class Event(Traitable):
    ...

if __name__ == '__main__':

    from core_10x.trait_filter import OR, BETWEEN, GE, NE, f

    e = Event()
    print(e.id())

    p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    print(p.id(), p.full_name)

    p.full_name = 'Ilya Pevzner'
    print(p.full_name)
    print(f'first name = {p.first_name}; last name = {p.last_name}')

    p.age = 61

    print(f'older_than(25) = {p.older_than(25)}')

    try:
        p.older_than = False
    except TypeError as ex:
        print(ex)

    p.older_than = trait_value(False, 25)   #-- set with args!
    print(f'older_than(25) = {p.older_than(25)}')

    print(p.from_any(p.trait.older_than(), 'False'))

    r = OR(
        f(age = BETWEEN(50, 70), first_name = NE('Sasha') ),
        f(age = 17)
    )

    print(r.prefix_notation())
    print(r.eval(p))

