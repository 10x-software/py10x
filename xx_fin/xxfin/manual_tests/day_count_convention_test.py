from datetime import date, timedelta

from core_10x.logger import PerfTimer

#from xxfin.day_count_convention import DAY_COUNT_CONVENTION


def test_data(start_date: date, n: int) -> list:
    res = []
    dt = 1
    sdir = DAY_COUNT_CONVENTION.s_dir
    for _i in range(n):
        for f in sdir.values():
            d = start_date + timedelta(days = dt)
            dt += 1
            v = f(start_date, d)
            res.append(v)

    return res

def test_perf(start_date: date, n: int):
    dt = 100
    with PerfTimer() as t:
        d = start_date + timedelta(days = dt)
        DAY_COUNT_CONVENTION.ACT360(start_date, d)
        DAY_COUNT_CONVENTION.ACT365(start_date, d)
        DAY_COUNT_CONVENTION.ACTACT(start_date, d)
        DAY_COUNT_CONVENTION.BB30360(start_date, d)
        DAY_COUNT_CONVENTION.US30360(start_date, d)
        DAY_COUNT_CONVENTION.EB30360(start_date, d)

    return t.elapsed

if __name__ == '__main__':

    d1 = date(2010, 3, 11)
    d2 = date(2026, 6, 12)
    n = 1000

    from xxfin.py_day_count_convention import DAY_COUNT_CONVENTION
    res1 = test_data(d1, n)
    t1 = test_perf(d1, n)

    from xxfin.cxx_day_count_convention import DAY_COUNT_CONVENTION  # noqa: F811
    res2 = test_data(d1, n)
    t2 = test_perf(d1, n)

    rc = all(r1 == r2 for r1, r2 in zip(res1, res2))
    acc = t1/t2



