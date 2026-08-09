if __name__ == '__main__':
    from core_10x.exec_control import GRAPH_ON
    from xxcommon.rdate import RDate

    from xxfin.fx_forward_curve import FXForwardCurve, FXForwardCurveSimple
    from xxfin.fx_forward_curve_mas import FxForwardCurveMas
    from xxfin.fx_mkt_conventions import FXMktConventions
    from xxfin.fx_spot_fwd_quotable import FXForwardQuotable, FXSpotQuotable
    from xxfin.pricing_context import PricingContext

    btp = GRAPH_ON()
    btp.begin_using()

    crosses   = [ 'GBP/USD', 'EUR/USD', 'USD/JPY']
    # crosses = ['GBP/USD']


    pc = PricingContext.current()

    provider    = pc.mkt_data_provider_name
    md_date     = pc.md_date
    snapshot    = pc.snapshot

    eps = 1.e-10

    pc = PricingContext.current()
    provider = pc.mkt_data_provider_name
    md_date = pc.md_date
    snapshot = pc.snapshot

    fxmas = FxForwardCurveMas.s_data_per_market

    quotes = {}
    for cross in crosses:
        print(f'collecting {cross} quotes')
        mc = FXMktConventions.existing_instance(mkt_name=cross)
        spotdate = mc.spot_date(md_date)
        cal = mc.calendar
        roll = mc.roll_rule
        # print(f'test {cross} - cal= {cal}, roll = {roll}, spot date = {spot}')

        dates = []
        rates = []
        rdates = []
        spotrate = FXSpotQuotable(mkt_name=cross, provider_name=provider, md_date=md_date, snapshot=snapshot).quote
        dates.append(spotdate)
        rates.append(spotrate)
        rdates.append('spot')

        rdates = [RDate(r.strip()) for r in fxmas[cross][FXForwardQuotable].split(',')]
        for rd in rdates:
            d = rd.apply(spotdate, cal, roll) if rd.symbol() != '1B' else rd.apply(md_date, cal, roll)
            dates.append(d)
            r = FXForwardQuotable(mkt_name=cross, tenor=rd, provider_name=provider, md_date=md_date,
                                  snapshot=snapshot).quote
            rates.append(r)
            print(f'{cross} - {rd}/{d} - quoted: {r}')
        rdates.insert(0, 'spot')
        print('--------------------------')

        quotes[cross] = (rdates, dates, rates)

    print('\ntesting ==== FXForwardCurveSimple ====\n')
    for cross, (rdates, dates, rates) in quotes.items():
        fxc_object = FXForwardCurveSimple(
            provider_name=provider,
            md_date=md_date,
            snapshot=snapshot,
            mkt_name=cross
        )
        fxc = fxc_object.payload
        for rd, d, r in zip(rdates, dates, rates):
            calc = fxc.value(d)
            print(f'{cross} - {rd}/{d} - quoted: {r}, single_cross_rate calc: {calc}')
            assert abs(r - calc) < eps

        print(f'----- done with {cross} ----\n')

    print('\ntesting ==== FXForwardCurve ====\n')
    for cross, (rdates, dates, rates) in quotes.items():
        fxc_object = FXForwardCurve(
            provider_name=provider,
            md_date=md_date,
            snapshot=snapshot,
            mkt_name=cross
        )
        fxc = fxc_object.payload
        for rd, d, r in zip(rdates, dates, rates):
            calc = fxc.value(d)
            print(f'{cross} - {rd}/{d} - quoted: {r}, single_cross_rate calc: {calc}')
            assert abs(r - calc) < eps

        print(f'----- done with {cross} ----\n')
