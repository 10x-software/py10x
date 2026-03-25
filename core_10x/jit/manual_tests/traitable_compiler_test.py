from numpy import random

from core_10x.logger import PerfTimer

from core_10x.jit.manual_tests.basic_test import Calc, RT

class XCalc(Calc):
    price_ccy: float    = RT()

    def price_ccy_get(self, r: float) -> float:
        return self.price * r

    def price_get(self):
        random.seed(self.seed)
        r = 0.
        for i in range(self.count):
            p = random.normal(self.avg, self.std)
            q = random.randint(1, self.max_qty)
            r += p * q

        self.feature(r)
        return r

    def feature(self, a):
        print(f'{self.__class__.__name__}.feature({a})')

if __name__ == '__main__':
    from datetime import datetime
    from core_10x.jit.traitable_compiler import TraitableCompiler, TraitEntry

    seed = int(datetime.utcnow().timestamp())
    calc = XCalc(seed = seed)

    with PerfTimer() as t:
        p1 = calc.price

    dt1 = t.elapsed

    with PerfTimer() as t:
        p2 = calc.price

    dt2 = t.elapsed


    entry = TraitableCompiler.compile_getter(XCalc, 'price', use_it = True)
    p = calc.price

    with PerfTimer() as t:
        p3 = calc.price

    dt3 = t.elapsed

    print(f'prices: {p1:.4f}, {p3:.4f}')
    print(f'acceleration: {dt1/dt3: .1f}')