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

class Dict(Traitable):
    payload: dict                       = T()


if __name__ == '__main__':
    from core_10x.manual_tests.traitable_serialization_test import MARRITAL_STATUS, Address, Person

    address = Address(street="145 Austin Dr", cszip="Burlington, VT 05401")
            
    woman       = Person(ssn = '008-59-6666', name = 'Alice Smith',     dob = date(1972, 8, 21), _replace = True)
    daughter    = Person(ssn = '008-77-7777', name = 'Ann Smith',       dob = date(1997, 6, 17), _replace = True)
    son         = Person(ssn = '008-99-5555', name = 'Nathan Smith',    dob = date(1999, 9, 23), _replace = True)


    man     = Person(_replace = True,
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

    from core_10x.package_refactoring import PackageRefactoring

    class_id = PackageRefactoring.find_class_id(Person)
    p_cls = PackageRefactoring.find_class(class_id)
    assert p_cls is Person

    man2 = Person.deserialize_object(Person.s_bclass, None, ss)
    print(man == man2)

    d1 = Dict(
        _replace    = True,
        payload     = {1: [1,1], 2: [2,2]}
    )
    s1 = d1.serialize_object()

    d2 = Dict.deserialize_object(Dict.s_bclass, None, s1)
    print(d1 == d2)

    d3 = Dict(
        _replace = True,
        payload = {
            woman:      1.0,
            daughter:   2.0,
            son:        -1.0
        }
    )
    s3 = d3.serialize_object()

    d4 = Dict.deserialize_object(Dict.s_bclass, None, s3)
    print(d3 == d4)
