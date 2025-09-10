from datetime import date
from core_10x.traitable import Traitable, AnonymousTraitable, T, THIS_CLASS
from core_10x.named_constant import NamedConstant

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
    from infra_10x.mongodb_store import MongoStore

    db = MongoStore.instance(hostname='localhost', dbname='test')
    db.begin_using()

    woman       = Person(ssn = '008-59-6666', name = 'Alice Smith',     dob = date(1972, 8, 21))
    daughter    = Person(ssn = '008-77-7777', name = 'Ann Smith',       dob = date(1997, 6, 17))
    son         = Person(ssn = '008-99-5555', name = 'Nathan Smith',    dob = date(1999, 9, 23))

    man     = Person(
        ssn     = '009-87-4444',
        name    = 'John Smith',
        gender  = True,
        dob     = date(1965, 2, 3),
        marrital_status = MARRITAL_STATUS.MARRIED,
        spouse = woman,
        children = [daughter, son],
        address = Address(street = '145 Austin Dr', cszip = 'Burlington, VT 05401')
    )

    ss = man.serialize_object()
    man2 = Person.deserialize_object(Person.s_bclass, None, ss)

    print(man == man2)

