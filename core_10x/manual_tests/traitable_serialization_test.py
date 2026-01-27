from datetime import date

from core_10x.named_constant import NamedConstant
from core_10x.traitable import THIS_CLASS, AnonymousTraitable, T, Traitable


class MARRITAL_STATUS(NamedConstant):
    SINGLE      = ()
    MARRIED     = ()
    DIVORCED    = ()
    WIDOWED     = ()

class Address(AnonymousTraitable):
    street: str     = T()
    cszip: str      = T()

class Person(Traitable):
    ssn: str                            = T(T.ID)

    dob: date                           = T()
    name: str                           = T()
    gender: bool                        = T()
    marrital_status: MARRITAL_STATUS    = T()

    spouse: THIS_CLASS                  = T()
    children: list                      = T()

    address: Address                    = T(T.EMBEDDED)

if __name__ == '__main__':
    address = Address(street="145 Austin Dr", cszip="Burlington, VT 05401")
            
    woman       = Person(ssn = '008-59-6666', name = 'Alice Smith',     dob = date(1972, 8, 21), _force = True)
    daughter    = Person(ssn = '008-77-7777', name = 'Ann Smith',       dob = date(1997, 6, 17), _force = True)
    son         = Person(ssn = '008-99-5555', name = 'Nathan Smith',    dob = date(1999, 9, 23), _force = True)


    man     = Person(_force = True,
        ssn     = '009-87-4444',
        name    = 'John Smith',
        gender  = True,
        dob     = date(1965, 2, 3),
        marrital_status = MARRITAL_STATUS.MARRIED,
        spouse = woman,
        children = [daughter, son],
        address = address
    )

    ss = man.serialize_object()

    man2 = Person.deserialize_object(Person.s_bclass, None, ss)

    print(man == man2)

