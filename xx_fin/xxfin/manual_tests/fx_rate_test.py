if __name__ == '__main__':

    from datetime import date

    from core_10x.exec_control import GRAPH_ON
    from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate

    from xxfin.ccy_cross import CcyCross
    from xxfin.fx_forward_curve_mas import FxForwardCurveMas
    from xxfin.fx_mkt_conventions import FXMktConventions
    from xxfin.fx_rate import FxRate
    from xxfin.fx_spot_fwd_quotable import FXForwardQuotable, FXSpotQuotable
    from xxfin.pricing_context import PricingContext


    btp = GRAPH_ON()
    btp.begin_using()

    TEST_QTD_RATE   = True
    TEST_RATE_Q     = True
    TEST_RATE_NON_Q = True


    crosses   = [ 'GBP/USD', 'EUR/USD', 'USD/JPY']
    # crosses   = [ 'EUR/USD']

    SPOT = True
    FWDS = True



    eps = 1.e-10


    if TEST_QTD_RATE or TEST_RATE_Q:
        pc = PricingContext.current()
        provider    = pc.mkt_data_provider_name
        md_date     = pc.md_date
        snapshot    = pc.snapshot

        fxmas = FxForwardCurveMas.s_data_per_market

        quotes = {}
        for cross in crosses:
            print(f'collecting {cross} quotes')
            mc      = FXMktConventions.existing_instance(mkt_name = cross)
            spotdate= mc.spot_date(md_date)
            cal     = mc.calendar
            roll    = mc.roll_rule
            # print(f'test {cross} - cal= {cal}, roll = {roll}, spot date = {spot}')

            dates  = []
            rates  = []
            rdates = []
            if SPOT:
                spotrate= FXSpotQuotable(mkt_name = cross, provider_name = provider, md_date = md_date, snapshot=snapshot).quote
                dates.append(spotdate)
                rates.append(spotrate)
                rdates.append('spot')

            if FWDS:
                rdates  = [RDate(r.strip()) for r in fxmas[cross][FXForwardQuotable].split(',')]
                for rd in rdates:
                    d = rd.apply(spotdate, cal, roll) if rd.symbol() != '1B' else rd.apply(md_date, cal, roll)
                    dates.append(d)
                    r = FXForwardQuotable(mkt_name = cross, tenor = rd, provider_name = provider, md_date = md_date, snapshot=snapshot).quote
                    rates.append(r)
                    print(f'{cross} - {rd}/{d} - quoted: {r}')
                if SPOT:
                    rdates.insert(0,'spot')
            print('--------------------------')

            quotes[ cross ] = (rdates, dates, rates)


    if TEST_QTD_RATE:
        print('\ntesting ==== FxRate.quoted_cross_rate() ====\n')
        for cross, (rdates, dates, rates ) in quotes.items():
            for rd, d, r in zip(rdates, dates, rates):
                calc = FxRate.quoted_cross_rate(CcyCross.existing_instance(cross = cross), d, provider, md_date, snapshot)
                print(f'{cross} - {rd}/{d} - quoted: {r}, single_cross_rate calc: {calc}')
                assert abs(r - calc) < eps

            print(f'----- done with {cross} ----\n')

    if TEST_RATE_Q:
        print('\ntesting ==== FxRate(cross).rate() for quoted crosses ====\n')
        for cross, (rdates, dates, rates) in quotes.items():
            fxr_obj = FxRate(cross_name = cross)
            for rd, d, r in zip(rdates, dates, rates):
                calc = fxr_obj.rate( d )
                print(f'{cross} - {rd}/{d} - quoted: {r}, rate calc: {calc}')
                assert abs(r - calc) < eps

            print(f'----- done with {cross} ----\n')

    if TEST_RATE_NON_Q:
        print('\ntesting ==== FxRate(cross).rate() for implied crosses ====\n')
        d = date(2030,1,1)
        split = [
            dict(
                crs = 'EUR/GBP',
                top = 'EUR/USD',
                btm = 'GBP/USD',
                t   = 1,
                b   = 1,
            ),
            dict(
                crs = 'GBP/CAD',
                top = 'GBP/USD',
                btm = 'USD/CAD',
                t   =  1,
                b   = -1,
            ),
            dict(
                crs = 'JPY/CAD',
                top = 'USD/JPY',
                btm = 'USD/CAD',
                t   = -1,
                b   = -1,
            ),
            dict(
                crs = 'JPY/GBP',
                top = 'USD/JPY',
                btm = 'GBP/USD',
                t   = -1,
                b   =  1,
            )

        ]
        for sp in split:
            rc = FxRate(cross_name = sp['crs']).rate(d)
            rt = FxRate(cross_name = sp['top']).rate(d)
            rb = FxRate(cross_name = sp['btm']).rate(d)
            t  = sp['t']
            b  = sp['b']
            ri = rt**t/rb**b
            print(f'{sp["crs"]} - implied = {rc} , calc = {ri}')
            assert abs(rc - ri) < eps


        same_ccy = ['USD/USD', 'AED/AED']
        for c in same_ccy:
            r = FxRate(cross_name = c).rate(d)
            print(f'{c} - implied = {r} , calc = 1.')
            assert r == 1.


        d = date(2030,1,1)
        same_ccy = ['USD/USD', 'GBP/GBP']
        for c in same_ccy:
            r = FxRate(cross_name = c).rate(d)
            print(f'{c} - implied = {r} , calc = 1.')
            assert r == 1

        # same_ccy = ['XXX/XXX', 'AED/AED']
        # for c in same_ccy:
        #     r = FxRate(cross_name = c).rate(d)



        print('--------------------------')
