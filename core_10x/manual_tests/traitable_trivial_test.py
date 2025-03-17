from datetime import datetime, date

from core_10x.code_samples.person import Person
from core_10x.traitable import Traitable, trait_value, T
from core_10x.exec_control import ProcessContext

class Event(Traitable):
    at: datetime = T()


if __name__ == '__main__':
    ProcessContext.set_flags(ProcessContext.CACHE_ONLY)

    e = Event()
    print(e.id())
    rc = e.set_values(at = datetime.now())

    p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    print(p.id(), p.full_name)

    p.full_name = 'Ilya Pevzner'
    print(p.full_name)
    print(f'first name = {p.first_name}; last name = {p.last_name}')

    p.dob = date(1963, 5, 14)
    #p.age = 61

    print(f'older_than(25) = {p.older_than(25)}')

    try:
        p.older_than = False
    except TypeError as ex:
        print(ex)

    p.older_than = trait_value(False, 25)   #-- set with args!
    print(f'older_than(25) = {p.older_than(25)}')

    print(p.from_any(p.T.older_than(), 'False'))

    p2 = Person(first_name = 'Sasha', last_name = 'Davidovich')
    assert p2.age == 61

    #print(Nucleus.serialize_any(p,False))