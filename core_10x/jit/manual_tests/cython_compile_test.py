from numpy import random
from math import sin

def Calc_price_get(self):
    print('***Python***')
    random.seed(self.seed)

    self_count = self.count
    self_avg = self.avg
    self_std = self.std
    self_max_qty = self.max_qty

    random_normal = random.normal
    random_randint = random.randint

    r = 0.0
    for i in range(self_count):
        p = random_normal(self_avg, self_std)
        #q = random_randint(1, self_max_qty)
        #r += p * q
        r += p

    return r


def Calc_abracadabra_get(self):
    print('***Python***')

    count = self.count
    avg = self.avg

    # r = 0.
    # for i in range(count):
    #     p = avg + i
    #     r += p
    #
    # return r

    return sum(avg + i for i in range(count))

if __name__ == '__main__':
    """
    Target Layout:
    core_10x/
      jit/
        manual_tests/
          basic_test.py
          cython/
             basic_test_cython.pyx
             basic_test_cython.pyd   (compiled)
    """
    from core_10x.jit.manual_tests._cy.basic_test_cython import Calc_price_get as Cython_price, Calc_abracadabra_get as Cython_abracadabra

    from core_10x.jit.manual_tests.basic_test import Calc, PerfTimer

    c = Calc(seed = 123)
    c.count = 100_000

    with PerfTimer() as t:
        p = c.price
    dt = t.elapsed

    trait = Calc.trait('price')
    trait.set_f_get(Calc_price_get, True)

    with PerfTimer() as t:
        p2 = c.price
    dt2 = t.elapsed

    trait.set_f_get(Cython_price, True)
    with PerfTimer() as t:
        p3 = c.price
    dt3 = t.elapsed

    print(f'prices: {p}, py: {p2}, cy: {p3}')
    print(f'acc = Py: {dt/dt2}, Cy: {dt/dt3}')
