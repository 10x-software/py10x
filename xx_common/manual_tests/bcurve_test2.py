if __name__ == '__main__':

    import numpy as np


    from datetime import date, timedelta

    from core_10x.xdate_time import XDateTime
    from core_10x.logger import PerfTimer

    import math

    def test1() -> tuple:
        c = DateCurve()

        with PerfTimer() as t_create:
            c.update_many(dates, values)

        with PerfTimer() as t_interp:
            interps = c.values_at(rand_dates)

        return (c.values, t_create.elapsed, interps, t_interp.elapsed)

    val_mult = 0.5
    # val_mult = math.pi

    num_date_steps = 1000
    date_step = 10

    d1 = date(2020, 2, 1)
    dt = timedelta(days=date_step)
    dates = []
    values = []
    d = d1
    v = 1. * val_mult
    for i in range(num_date_steps):
        dates.append(d)
        values.append(v)
        d = d + dt
        v = v + 2 * val_mult
    # rdt = timedelta(days=20)

    # low < 0 or high > 20000 -> extrapolation
    # lo = 50000     # 0
    # hi = 70000  # 10000
    # sz = 20000
    # rand_int   = np.random.randint(lo, hi, size=sz)
    # rand_dates = [d1 + timedelta(days=int(rand)) for rand in rand_int]

    def t_str(tns) -> str:
        ts = tns * 1e-9
        t_hr,  tx    = divmod( ts, 3600 )
        t_min, t_sec = divmod( tx, 60   )

        return f'{t_min} min ' if t_min else '' + f'{t_sec} sec'


    num_dates_from_start = num_date_steps * date_step

    sz = num_dates_from_start * 2

    cases = [
        dict( case = 'left extrap far away',    lo = -num_dates_from_start * 5, hi = -num_dates_from_start * 2, sz = sz ),
        dict( case = 'left extrap not far',     lo = -num_dates_from_start * 2, hi = -1,                        sz = sz ),
        dict( case = 'interpolation',           lo = 0,                         hi = num_dates_from_start,      sz = sz ),
        dict( case = 'right extrap not far',    lo = num_dates_from_start + 1,  hi = num_dates_from_start * 3,  sz = sz ),
        dict( case = 'right extrap far away',   lo = num_dates_from_start * 5,  hi = num_dates_from_start * 8,  sz = sz ),
    ]

    with PerfTimer() as t_test:
        for case in cases:
            rand_dates = [d1 + timedelta(days=int(rand)) for rand in np.random.randint(case['lo'], case['hi'], size=case['sz'])]


            from xx_common.py_curve import DateCurve, IP_KIND
            py_vals, py_dt, py_interps, py_dt_interp = test1()

            from xx_common.cxx_curve import DateCurve, IP_KIND
            cxx_vals, cxx_dt, cxx_interps, cxx_dt_interp = test1()


            assert len(py_vals) == len(cxx_vals)
            assert len(py_interps) == len(cxx_interps)

            print(f'{case["case"]}: lo = {case["lo"]}, hi = {case["hi"]}, interp sample size = {case["sz"]}')
            print( f'\tsq diff of vals = {sum((c-p)**2 for (c, p) in zip(cxx_vals, py_vals))}')
            # print( f'size of interps: {len(py_interps)}')
            # print( f'avg sq diff of interps = {(sum((c-p)**2 for (c, p) in zip(cxx_interps, py_interps)))/len(py_interps)}')
            print( f'\tavg sq diff of interps = {(sum((c-p)**2 for (c, p) in zip(cxx_interps, py_interps)))/case["sz"]}')

            print(f'\tratio of create times: {py_dt/cxx_dt}')
            print(f'\tratio of interp times: {py_dt_interp/cxx_dt_interp}')
            print(f'\n')

    print('\n\n')
    print(f'test cases: {len(cases)}, each test size: {sz}')
    print(f'total execution time: {t_str(t_test.elapsed)}')
