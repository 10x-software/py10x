from core_10x.code_samples.person import Person
from core_10x.xnone import XNone
from core_10x.exec_control import GRAPH_ON, GRAPH_OFF, BTP

def test():
    p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    #p.weight_lbs = 100
    #assert p.weight == 100

    p.invalidate_value(p.T.weight)
    p.invalidate_value(p.T.weight_lbs)

    assert p.weight is XNone

if __name__ == '__main__':

    with GRAPH_ON(convert_values = True, debug = True):
        print(BTP.current().flags())
        test()
        with GRAPH_OFF():
            test()

    p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    with GRAPH_ON(convert_values = True):
        p.weight_lbs = 'a'


