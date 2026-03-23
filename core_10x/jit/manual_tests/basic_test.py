import random
from datetime import datetime

from core_10x.traitable import Traitable, T, RT
from core_10x.exec_control import GRAPH_ON
from core_10x.logger import PerfTimer

class Calc(Traitable):
    count: int      = RT(10**4)

    seed: int       = RT()
    avg: float      = RT(1.)
    std: float      = RT()
    max_qty: int    = RT(100)

    price: float    = RT()

    def seed_get(self):
        return int(datetime.utcnow().timestamp())

    def std_get(self):
        return self.avg / 10.

    def price_get(self):
        r = 0.
        for i in range(self.count):
            p = random.gauss(self.avg, self.std)
            q = random.randint(1, self.max_qty)
            r += p * q

        return r

if __name__ == '__main__':
    from core_10x.jit.getter_compiler import GetterCompiler

    graph = GRAPH_ON()
    graph.begin_using()

    calc = Calc()
    seed = calc.seed
    random.seed(seed)

    with PerfTimer() as t1:
        p1 = calc.price

    dt1 = t1.elapsed

    trait_name = 'price'
    gc = GetterCompiler(traitable_class = Calc, trait_name = trait_name)
    trait = Calc.trait(trait_name)
    trait.set_f_get(gc.modified_getter, True)

    with PerfTimer() as t2:
        p2 = calc.price

    dt2 = t2.elapsed

    print(f'prices: {p1:.4f}, {p2:.4f}')
    print(f'acceleration: {dt1/dt2: .1f}')