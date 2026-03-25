from numpy import random
import numba

from core_10x.jit.manual_tests.basic_test import Calc, PerfTimer

class PlainCalc:
    def __init__(self, c: Calc):
        self.seed = c.seed
        self.count = c.count    #10_000
        self.avg = c.avg
        self.std = c.std
        self.max_qty = c.max_qty

    def feature(self, a):
        pass

    def set_seed(self):
        random.seed(self.seed)

    def next_p(self):
        return random.normal(self.avg, self.std)

    def next_q(self):
        return random.randint(1, self.max_qty)

    def price(self):
        r = 0.0
        self.set_seed()
        for i in range(self.count):
            p = self.next_p()
            q = self.next_q()
            r += p * q
        self.feature(r)
        return r

@numba.njit
def set_seed(seed):
    random.seed(seed)

@numba.njit
def next_p(avg, std):
    return random.normal(avg, std)

@numba.njit
def next_q(max_qty):
    return random.randint(1, max_qty)

@numba.njit
def feature(r):
    print(r)

@numba.njit
def price_for_numba(self_seed, self_count, self_avg, self_std, self_max_qty):
    r = 0.0
    set_seed(self_seed)
    for i in range(self_count):
        p = next_p(self_avg, self_std)
        q = next_q(self_max_qty)
        r += p * q
    feature(r)
    return r


if __name__ == '__main__':
    seed = 123
    calc = Calc(seed = seed)
    c = PlainCalc(calc)

    with PerfTimer() as t:
        p = c.price()
    dt = t.elapsed

    price_for_numba(c.seed, c.count, c.avg, c.std, c.max_qty)

    with PerfTimer() as t:
        numba_p = price_for_numba(c.seed, c.count, c.avg, c.std, c.max_qty)
    dt_numba = t.elapsed

    print(f'price = {p}, numba = {numba_p}')
    print(f'accelaration = {dt/dt_numba}')

    #print('COMPILING WITH numba.jit CHANGES numpy.random SEQUENCE! (compiling with numba.njit - works)')