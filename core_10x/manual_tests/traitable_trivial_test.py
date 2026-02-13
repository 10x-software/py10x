from datetime import date, datetime

from core_10x.code_samples.person import Person
from core_10x.traitable import T, RT, Traitable, Trait, BTraitFlags


class Event(Traitable):
    at: datetime = T()

class Dummy(Traitable):
    name: str       = T(T.ID)
    payload: float  = T(3.1415)

    view: str       = RT()

    def name_get(self):
        return 'AMD'

    def view_get(self) -> str:
        print(f'{self.__class__}.view called')
        return f'{self.name}: {self.payload}'

if __name__ == '__main__':
    from core_10x.manual_tests.traitable_trivial_test import Dummy, Event

    e = Event()
    print(e.id_value())
    rc = e.set_values(at = datetime.now())

    p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    #print(p.id(), p.full_name)

    # p.full_name = 'Ilya Pevzner'
    # print(p.full_name)
    # print(f'first name = {p.first_name}; last name = {p.last_name}')

    p.dob = date(1963, 5, 14)
    #p.age = 61

    #print(f'older_than(25) = {p.older_than(25)}')

    #try:
    #    p.older_than = False
    #except TypeError as ex:
    #    print(ex)

    #p.older_than = trait_value(False, 25)   #-- set with args!
    #print(f'older_than(25) = {p.older_than(25)}')

    #print(p.from_any(p.T.older_than(), 'False'))

    p2 = Person(first_name = 'Sasha', last_name = 'Davidovich')
    #assert p2.age == 61
    print(p2.age)

    #print(Nucleus.serialize_any(p,False))

    name = 'AMD'
    d = Dummy()
    assert d.name == name
    d.payload = 100.

    d2 = Dummy(name = name)
    assert d2.name == d.name

    dx = Dummy.existing_instance(name = name)
    assert dx.payload == 100.

    dx2 = Dummy.existing_instance()
    assert dx2.payload == 100.

    fn_t    = Person.trait('first_name')
    wqu_t   = Person.trait('weight_qu')
    w_t     = Person.trait('weight')

    print(f'first_name = {fn_t.has_custom_getter()}; weight_qu = {wqu_t.has_custom_getter()}; weight = {w_t.has_custom_getter()}')

    p3 = Person(_replace = True, first_name = 'S2', last_name = 'Davidovich2', dob = date(1963, 1, 1), weight_lbs = 250.)
    rc = p3.verify()
    if not rc:
        print(rc.error())

    p4 = Person(_replace = True, first_name = 'S', last_name = 'Davidovich', dob = date(1963, 1, 1), weight_lbs = 250.)
    rc = p4.verify()
    if not rc:
        print(rc.error())

    v = d.view
    v2 = d.view, d.view
    d.payload = -1000
    v2 = d.view
