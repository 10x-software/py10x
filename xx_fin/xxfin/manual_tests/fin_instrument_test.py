if __name__=='__main__':
    from datetime import date

    from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate

    from xxfin.ccy import Ccy
    from xxfin.ccy_forward import CcyForward, CcyUnit
    from xxfin.fin_calendar import FinCalendar
    from xxfin.fx_forward_curve import FXForwardCurveSimple
    from xxfin.ir_cash_deposit_quotable import IRCashDepositQuotable
    from xxfin.ir_swap_quotable import IRSwapQuotable
    from xxfin.ir_zero_rate_curve import ZeroRateCurve
    from xxfin.pricing_context import PricingContext


    pc = PricingContext.current()
    md_basis = pc.md_basis

    usd_cu = CcyUnit.existing_instance(denominated = Ccy('USD'))
    gbp_cu = CcyUnit.existing_instance(denominated = Ccy('GBP'))
    cad_cu = CcyUnit.existing_instance(denominated = Ccy('CAD'))

    usd_cf = CcyForward.existing_instance(denominated = Ccy('USD'), end_date = date(2026,8,4))
    gbp_cf = CcyForward.existing_instance(denominated = Ccy('GBP'), end_date = date(2026,8,4))
    cad_cf = CcyForward.existing_instance(denominated = Ccy('CAD'), end_date = date(2026,8,4))

    d6m_us = RDate('6M').apply(pc.md_date, FinCalendar('US'), BIZDAY_ROLL_RULE.FOLLOWING)
    d6y_us = RDate('6Y').apply(pc.md_date, FinCalendar('US'), BIZDAY_ROLL_RULE.FOLLOWING)
    d2y_gb = RDate('1Y').apply(pc.md_date, FinCalendar('GB'), BIZDAY_ROLL_RULE.FOLLOWING)
    d3y_gb = RDate('3Y').apply(pc.md_date, FinCalendar('GB'), BIZDAY_ROLL_RULE.FOLLOWING)
    usd_cf_6m = CcyForward.existing_instance(denominated = Ccy('USD'), end_date = d6m_us)
    usd_cf_6y = CcyForward.existing_instance(denominated = Ccy('USD'), end_date = d6y_us)
    gbp_cf_2y = CcyForward.existing_instance(denominated = Ccy('GBP'), end_date = d2y_gb)
    gbp_cf_3y = CcyForward.existing_instance(denominated = Ccy('GBP'), end_date = d3y_gb)

    gbp_fxc = FXForwardCurveSimple(mkt_name = 'GBP/USD', **md_basis)
    cad_fxc = FXForwardCurveSimple(mkt_name = 'USD/CAD', **md_basis)

    usd_zrc = ZeroRateCurve(mkt_name = 'SOFR',  **md_basis)
    gbp_zrc = ZeroRateCurve(mkt_name = 'SONIA', **md_basis)
    cad_zrc = ZeroRateCurve(mkt_name = 'CORRA', **md_basis)

    sofr_cash_depos = [
        IRCashDepositQuotable.existing_instance(tenor = RDate('1B'),  mkt_name = 'SOFR', **md_basis),
        IRCashDepositQuotable.existing_instance(tenor = RDate('1W'),  mkt_name = 'SOFR', **md_basis),
        IRCashDepositQuotable.existing_instance(tenor = RDate('1M'),  mkt_name = 'SOFR', **md_basis),
        IRCashDepositQuotable.existing_instance(tenor = RDate('3M'),  mkt_name = 'SOFR', **md_basis),
        IRCashDepositQuotable.existing_instance(tenor = RDate('6M'),  mkt_name = 'SOFR', **md_basis),
        IRCashDepositQuotable.existing_instance(tenor = RDate('9M'),  mkt_name = 'SOFR', **md_basis),
        IRCashDepositQuotable.existing_instance(tenor = RDate('12M'), mkt_name = 'SOFR', **md_basis),
    ]
    sofr_swaps = [
        IRSwapQuotable.existing_instance(tenor = RDate('5Y'),   mkt_name = 'SOFR', **md_basis),
        IRSwapQuotable.existing_instance(tenor = RDate('10Y'),  mkt_name = 'SOFR', **md_basis),
        IRSwapQuotable.existing_instance(tenor = RDate('20Y'),  mkt_name = 'SOFR', **md_basis),
        IRSwapQuotable.existing_instance(tenor = RDate('30Y'),  mkt_name = 'SOFR', **md_basis),
    ]

    sonia_cash_depos = [
        IRCashDepositQuotable.existing_instance(tenor = RDate('1B'),  mkt_name = 'SONIA', **md_basis),
        IRCashDepositQuotable.existing_instance(tenor = RDate('1W'),  mkt_name = 'SONIA', **md_basis),
        IRCashDepositQuotable.existing_instance(tenor = RDate('1M'),  mkt_name = 'SONIA', **md_basis),
        IRCashDepositQuotable.existing_instance(tenor = RDate('3M'),  mkt_name = 'SONIA', **md_basis),
        IRCashDepositQuotable.existing_instance(tenor = RDate('6M'),  mkt_name = 'SONIA', **md_basis),
        IRCashDepositQuotable.existing_instance(tenor = RDate('9M'),  mkt_name = 'SONIA', **md_basis),
        IRCashDepositQuotable.existing_instance(tenor = RDate('12M'), mkt_name = 'SONIA', **md_basis),
    ]
    sonia_swaps = [
        IRSwapQuotable.existing_instance(tenor = RDate('5Y'),   mkt_name = 'SONIA', **md_basis),
        IRSwapQuotable.existing_instance(tenor = RDate('10Y'),  mkt_name = 'SONIA', **md_basis),
        IRSwapQuotable.existing_instance(tenor = RDate('20Y'),  mkt_name = 'SONIA', **md_basis),
        IRSwapQuotable.existing_instance(tenor = RDate('30Y'),  mkt_name = 'SONIA', **md_basis),
    ]

    mkt_deps_cases = [
        ((usd_cf_6m, usd_cf_6y), (sofr_cash_depos,  sofr_swaps)),
        ((gbp_cf_2y, gbp_cf_3y), (sonia_cash_depos, sonia_swaps)),
    ]

    for mdc in mkt_deps_cases:
        secs = mdc[0]
        cash_depos, swaps = mdc[1]
        for cf in secs:
            print(f'cf = {cf}')
            ed = cf.max_date()
            print(f'{cf}: ed = {ed}')
            cds = []
            for cd in cash_depos:
            # for cd in sofr_cash_depos:
                cds.append(cd)
                print(f'{cd} pay date = {cd.pay_date}')
                if cd.pay_date > ed:
                    print(f'{cf}: last used cash depo = {cd}/{cd.pay_date}')
                    break

            swps = []
            ## if the instrument max date > last cash depo "end" date then go into swaps
            if ed > cd.pay_date:
                for swp in swaps:
                # for swp in sofr_swaps:
                    swps.append(swp)
                    print(f'{swp} pay date = {swp.pay_dates[-1]}')
                    if swp.pay_date > ed:
                        print(f'{cf}: last used swap = {swp}/{swp.pay_dates[-1]}')
                    # if swp.pay_dates[-1] > ed:
                        break

            print(f'{cf}: cash depos = {cds}')
            print(f'{cf}: swaps      = {swps}')
            deps = {}
            if cds:
                deps[IRCashDepositQuotable] = cds
            if swps:
                deps[IRSwapQuotable] = swps
            print('manual deps =' )
            for cls, qts in deps.items(): print(f'\t{cls}:  {qts}')
            print('mkt deps =')
            for cls, qts in cf.mkt_deps_for_discounting.items(): print(f'\t{cls}:  {qts}')
            assert deps == cf.mkt_deps_for_discounting
            print('\n')
            # print(f'{usd_zrc}: zrc quotables by class: {usd_zrc.quotables_by_class}')
            # print(f'{usd_zrc}: zrc quotables map:')
            # dates, quotables = usd_zrc.dates_quotables_map
            # print(f'\t{dates}')
            # print(f'\t{quotables}')