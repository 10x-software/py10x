
if __name__ == '__main__':
    from datetime import date

    # from xxcommon.cxx_curve import DateCurve

    d1 = date(2019, 12, 31)
    d2 = date(2020, 12, 31)
    r1 = 0.1
    r2 = 0.2

    dates  = [d1, d2]
    values = [r1, r2]

    d05 = d1 + (d2-d1)/2
    r05 = (r1+r2)/2
    eps = 1.e-10
    # d0 = date(2020, 7, 1)

    dd = [d1, d05, d2]

    from xxcommon.py_curve import DateCurve
    dcp = DateCurve(dates = dates, values = values)

    # d = d2
    for d in dd:
        rp = dcp.value(d)
        print(f'python DateCurve: {d} -> {rp}')
    assert abs(dcp.value(d05) - r05) < eps
    print()

    from xxcommon.cxx_curve import DateCurve
    dcc = DateCurve(dates = dates, values = values)
    for d in dd:
        rc = dcc.value(d)
        print(f'cxx DateCurve: {d} -> {rc}')
    assert abs(dcc.value(d05) - r05) < eps


