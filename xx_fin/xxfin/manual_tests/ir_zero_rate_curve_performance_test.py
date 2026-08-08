if __name__ == '__main__':
    from datetime import date, timedelta

    from core_10x.logger import PerfTimer
    from xxcommon.xxcommon_env_vars import XXCommonEnvVars

    from xxfin.ir_zero_rate_curve import ZeroRateCurve
    from xxfin.snapshot import SNAPSHOT
    from xxfin.xxfin_env_vars import XXFinEnvVars

    md_date = date(2025, 10, 10)    ## not steep
    sofr = dict(
        provider_name   = 'XX_DEV',
        mkt_name        = 'SOFR',
        # md_date         = date(2025, 3, 12),  ## flat
        # md_date         =date(2025, 5, 22),   ## hump
        # md_date         =date(2025, 5, 30),   ## flat (?)
        # md_date         =date(2025, 7, 3),    ## super steep
        md_date         = md_date,
        snapshot        = SNAPSHOT.CLOSE,
    )

    dates = [md_date + timedelta(days = i) for i in range(1000)]
    # sonia = dict(
    #     provider_name   ='XX_DEV',
    #     mkt_name        ='SONIA',
    #     # md_date         = date(2025, 3, 12),  ## flat
    #     # md_date         =date(2025, 5, 30),   ## steep
    #     md_date         =date(2025, 5, 22),   ## downward
    #     # md_date         =date(2025, 7, 3),    ## super steep ; start < 0
    #     # md_date         =date(2025, 10, 10),    ## not steep; start < 0
    #     snapshot        =SNAPSHOT.CLOSE,
    # )
    #

    def calc(zrc: ZeroRateCurve) -> tuple:
        with PerfTimer() as t:
            res = zrc.payload

        return (t.elapsed, res.dates_values())

    def using(zrc: ZeroRateCurve):
        rcurve = zrc.payload
        with PerfTimer() as t:
            for d in dates:
                rcurve.accrual(d)

        return t.elapsed

    #-- python version
    zrc = ZeroRateCurve(**sofr)
    mas = zrc.mkt_assembly_object
    calc(zrc)
    py_dt, py_dates_values = calc(zrc)
    py_dt2 = using(zrc)

    #-- c++ version
    XXCommonEnvVars.use_cxx_curve = True
    XXFinEnvVars.use_cxxfin = True

    #-- re-import what's needed!
    import importlib

    import xxcommon.curve

    import xxfin.cxx_rate_curve
    import xxfin.cxx_zrc_bootstrap
    import xxfin.day_count_convention
    import xxfin.ir_compounding
    import xxfin.ir_zero_rate_curve
    import xxfin.py_rate_curve
    import xxfin.py_zrc_bootstrap
    import xxfin.rate_curve
    import xxfin.zrc_bootstrap

    importlib.reload(xxcommon.curve)
    importlib.reload(xxfin.day_count_convention)
    importlib.reload(xxfin.ir_compounding)
    importlib.reload(xxfin.py_rate_curve)
    importlib.reload(xxfin.cxx_rate_curve)
    importlib.reload(xxfin.rate_curve)
    importlib.reload(xxfin.py_zrc_bootstrap)
    importlib.reload(xxfin.cxx_zrc_bootstrap)
    importlib.reload(xxfin.zrc_bootstrap)
    importlib.reload(xxfin.ir_zero_rate_curve)

    from xxfin.ir_zero_rate_curve import ZeroRateCurve

    zrc_cxx = ZeroRateCurve(**sofr)
    calc(zrc_cxx)
    cxx_dt, cxx_dates_values = calc(zrc_cxx)
    cxx_dt2 = using(zrc_cxx)

    #assert py_dates_values == cxx_dates_values
    print('==== checking date_values')
    for i in range(len(py_dates_values)):
        py_d, py_v = py_dates_values[i]
        cxx_d, cxx_v = cxx_dates_values[i]
        assert py_d == cxx_d, 'dates not match'
        eps = abs(py_v - cxx_v)
        assert eps < 1.e-12, f'{i}: EPS = {eps}'

    print('====== BUILDING times ======')
    print(f'Python:  {py_dt * 1000:.1f} ms')
    print(f'C++:     {cxx_dt * 1000:.1f} ms')
    print(f'Speedup: {py_dt / cxx_dt:.1f}x')

    print('====== USING times ======')
    print(f'Python:  {py_dt2 * 1000:.1f} ms')
    print(f'C++:     {cxx_dt2 * 1000:.1f} ms')
    print(f'Speedup: {py_dt2 / cxx_dt2:.1f}x')

