from core_10x.xnone import XNone
from core_10x.code_samples.person import Person
from core_10x.exec_control import GRAPH_ON, GRAPH_OFF
from core_10x.ts_union import TsUnion


def test():
    p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    #p.weight_lbs = 100
    #assert p.weight == 100

    p.invalidate_value(p.T.weight)
    p.invalidate_value(p.T.weight_lbs)

    assert p.weight == XNone

if __name__ == '__main__':
    with TsUnion():
        with GRAPH_ON():
            test()
            with GRAPH_OFF():
                test()



