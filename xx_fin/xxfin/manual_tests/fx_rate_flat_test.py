"""
Flat, procedural equivalent of xxfin/unit_tests/test_fx_rate.py's three test methods -- no
classes, no unittest.TestCase, just the same operations in the same order.
"""

if __name__ == '__main__':
    from datetime import date

    from xxfin.ccy_cross import CcyCross
    from xxfin.fx_rate import FxRate
    from xxfin.pricing_context import PricingContext
    from xxfin.unit_tests.test_fx_rate import crosses, quotes

    pc = PricingContext.current()
    provider = pc.mkt_data_provider_name
    md_date  = pc.md_date
    snapshot = pc.snapshot

    print('=== test_quoted_cross_rate ===')
    for cross, (dates, rates) in quotes(crosses, provider, md_date, snapshot).items():
        for d, r in zip(dates, rates):
            calc = FxRate.quoted_cross_rate(CcyCross.existing_instance(cross=cross), d, provider, md_date, snapshot)
            assert abs(r - calc) < 1e-6, f'{cross} {d}: {r} != {calc}'
    print('OK')

    print('=== test_rate_non_q ===')
    d = date(2030, 1, 1)
    split = [
        dict(crs='EUR/GBP', top='EUR/USD', btm='GBP/USD', t=1, b=1),
        dict(crs='GBP/CAD', top='GBP/USD', btm='USD/CAD', t=1, b=-1),
        dict(crs='JPY/CAD', top='USD/JPY', btm='USD/CAD', t=-1, b=-1),
        dict(crs='JPY/GBP', top='USD/JPY', btm='GBP/USD', t=-1, b=1),
    ]
    for sp in split:
        rc = FxRate(cross_name=sp['crs']).rate(d)
        rt = FxRate(cross_name=sp['top']).rate(d)
        rb = FxRate(cross_name=sp['btm']).rate(d)
        assert abs(rc - rt ** sp['t'] / rb ** sp['b']) < 1e-6
    print('OK')

    print('=== test_rate_q ===')
    for cross, (dates, rates) in quotes(crosses, provider, md_date, snapshot).items():
        fxr_obj = FxRate(cross_name=cross)
        for d, r in zip(dates, rates):
            calc = fxr_obj.rate(d)
            assert abs(r - calc) < 1e-6
    print('OK')
