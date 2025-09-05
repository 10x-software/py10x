from datetime import date

from core_10x.xnone import XNone
from core_10x.code_samples.person import Person
from core_10x.exec_control import GRAPH_ON, GRAPH_OFF, CONVERT_VALUES_ON
from core_10x.ts_union import TsUnion


def _test1():
    p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    #p.weight_lbs = 100
    #assert p.weight == 100

    p.invalidate_value(p.T.weight)
    p.invalidate_value(p.T.weight_lbs)

    assert p.weight == XNone


def test_1():
    with TsUnion():
        with GRAPH_ON():
            _test1()
            with GRAPH_OFF():
                _test1()

def test_2():
    with TsUnion():
        p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    with CONVERT_VALUES_ON():
        p.set_values(dob='December 1, 2000')
    age = (date.today().toordinal() - p.dob.toordinal())/365.25
    assert int(age) == p.age, f'Expected age around {int(age)}, got {p.age}'

def test_3():
    with TsUnion():
        p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    p.dob = XNone
    print(p.serialize_object())

    with CONVERT_VALUES_ON():
        p.dob = 20051231999
    print(p.serialize_object())


if __name__ == '__main__':
    #test_1()
    #test_2()
    test_3()



