if __name__ == '__main__':
    from datetime import date

    from core_10x.exec_control import GRAPH_ON

    #import matplotlib
    from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate

    from xxfin.fin_calendar import FinCalendar
    from xxfin.fx_forward_curve import FXForwardCurve, FXForwardCurveSimple
    from xxfin.fx_mkt_conventions import FXMktConventions
    from xxfin.snapshot import SNAPSHOT

    # cross = 'EUR/USD'
    # cross = 'GBP/USD'
    # cross = 'USD/CHF'
    cross = 'USD/JPY'

    md_date = date(2025, 10, 10)

    btp = GRAPH_ON()
    btp.begin_using()

    mc = FXMktConventions.existing_instance(mkt_name = cross)

    gbp = dict(
        provider_name   = 'XX_DEV',
        mkt_name        = cross,
        md_date         = md_date,
        snapshot        = SNAPSHOT.CLOSE,
    )

    ffc = FXForwardCurve(**gbp)
    fx_fwd_curve = ffc.payload

    print(f'\nFX fwd curve {ffc} doesnt have its own dates (it just knows how to calc an fx forward rate off 2 other curves); check for dates of ccy-funded curve, funding curve and FXSimple curve')
    for dv in fx_fwd_curve.dates_values():
        print(f'{dv[0]} , {dv[1] * 100}')

    print(f'\nFX Curve values for dates of the ccy curve: {ffc.ccy_disc_curve} (should be the end dates of the mkt quotes)')
    ccy_curve = ffc.ccy_disc_curve.payload
    # print(f'ccy funded curve extrapolation params: {ccy_curve.params.bounds_error}/{ccy_curve.params.fill_value}/{ccy_curve.interpolator}')
    for d in ccy_curve.dates:
        print(f'{d} , {fx_fwd_curve.value(d)}')

    print(f'\nFX Curve values for dates of the funding curve: {ffc.funding_disc_curve} (end dates of the IR quotes in the funding ccy, unrelated to fx quote end dates)')
    funding_curve = ffc.funding_disc_curve.payload
    # print(f'funding curve extrapolation params: {funding_curve.params.bounds_error}/{funding_curve.params.fill_value}/{funding_curve.interpolator}')

    for d in funding_curve.dates:
        print(f'{d} , {fx_fwd_curve.value(d)}')

    fx_simple_fwd_curve = FXForwardCurveSimple(
        provider_name   = gbp['provider_name'],
        mkt_name        = gbp['mkt_name'     ],
        md_date         = gbp['md_date'      ],
        snapshot        = gbp['snapshot'     ],
    )
    fx_simple_curve = fx_simple_fwd_curve.payload
    print(f'\nFX Curve values for dates of the fx simple curve: {fx_simple_fwd_curve} ( = the end dates of the mkt quotes)')
    # print(f'fx simple curve extrapolation params (bounds_error/fill_value/interp): {fx_simple_curve.params.bounds_error}/{fx_simple_curve.params.fill_value}/{fx_simple_curve.params.interpolator}')
    print('FX Curve value, FX quote, the diff')
    for (d, v) in fx_simple_curve.dates_values():
        fv = fx_fwd_curve.value(d)
        print(f'{d} , {fv} , {v} , {fv-v}')

    '''
    print(f'\nCompare interpolated values of fx fwd curve vs fx simple curve')
    start = md_date
    step = RDate('1M')
    end = RDate('30Y').apply(max( ccy_curve.end_time(), funding_curve.end_time(), fx_simple_curve.end_time() ), FinCalendar.none(), BIZDAY_ROLL_RULE.NO_ROLL)
    d = start
    dd = fvv = fsv = diffs = []
    while d < end:
        dd.append(d)
        fvv.append(fv := fx_fwd_curve.value(d))
        fsv.append(fs := fx_simple_curve.value(d))
        diffs.append(diff := fv-fs )
        print(f'{d} , {fv}, {fs}, {diff}')
        d = step.apply(d, FinCalendar.none(), BIZDAY_ROLL_RULE.NO_ROLL)

    '''

    # import matplotlib.pyplotas as plt




