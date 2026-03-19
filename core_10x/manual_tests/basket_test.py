from core_10x.basket import Basket
from core_10x.code_samples.person import Person
from core_10x.xinf import XInf
from core_10x.named_constant import NamedCallable

class FEATURE(NamedCallable):
    A60     = lambda p: p.older_than(60)
    W200    = lambda p: p.weight >= 200

if __name__ == '__main__':

    all_people = Person.load_many()

    class AGGREGATOR(NamedCallable):
        WEIGHT     = lambda gen: sum(v*q for v, q in gen)

    #b = Basket.simple(Person)
    #b = Basket.by_feature(Person, FEATURE.W200)
    #b = Basket.by_breakpoints(Person, lambda p: p.weight, -XInf, 100, 170, 200, XInf)
    b = Basket.by_range(Person, Person.T.weight, ('underweight', -XInf, 100), ('normal', 170., 180.), ['overweight', 190., XInf])
    b.aggregator_class = AGGREGATOR

    #b = Basket.by_feature(Person, lambda p: p.weight, 190., 200.)
    #b = Basket.by_feature(Person, Person.T.weight, 190., 200.)

    for i, p in enumerate(all_people):
        b.add(p, i)

    #ta = Person.T.weight

    r = b.weight