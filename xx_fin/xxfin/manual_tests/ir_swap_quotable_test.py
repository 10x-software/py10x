
if __name__=='__main__':
    from datetime import date

    from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate
    from xxfin.fin_calendar import FinCalendar
    from xxfin.ir_rate_mkt_conventions import IRRateMktConventions
    from xxfin.ir_swap_quotable import IRSwapQuotable
    from xxfin.ir_zero_rate_curve import ZeroRateCurve
    from xxfin.pricing_context import PricingContext
    from xxfin.py_day_count_convention import DAY_COUNT_CONVENTION


    irate       = 'SOFR'
    cal         = FinCalendar('US')
    roll_rule   = BIZDAY_ROLL_RULE.MOD_FOLLOWING
    dc_conv     = DAY_COUNT_CONVENTION.ACT360
    swap_freq   = RDate('1Y')
    pay_delay   = RDate('2B')

    tenor_sym   = '5Y'

    pc = PricingContext.current()
    md_basis = pc.md_basis

    tenor = RDate(tenor_sym)
    sq = IRSwapQuotable(mkt_name = irate, tenor = tenor, **md_basis)
    print(f'{sq}: rate = {sq.mkt_name}, tenor = {sq.tenor}, quote = {sq.quote}')
    print(f'{sq}: start date = {sq.start_date}, end date = {sq.end_date}, pay date = {sq.pay_date}')
    print(f'{sq}:\n\tstart dates = {sq.start_dates},\n\tend dates   = {sq.end_dates},\n\tpay dates   = {sq.pay_dates}')
    print(f'{sq}: incr dcfs = {sq.incremental_dc_fractions}')
    print(f'{sq}: periods = {sq.periods()}')

    zrc_obj = ZeroRateCurve(mkt_name = irate, **md_basis)
    zrc = zrc_obj.payload

    print(f'{sq}: {tenor_sym} annuity = {sq.annuity_calc(zrc)}')
    for y in range(5):
        print(f'{sq}: {y+1} year annuity = {sq.annuity_calc(zrc, periods = y+1)}')

    mc = IRRateMktConventions(mkt_name = irate)
    swap_start_date = mc.spot_date(md_basis['md_date'])
    swap_end_date   = tenor.apply(swap_start_date, cal, roll_rule)
    end_dates = []
    non_rolled_ed = rolled_ed = swap_start_date
    while rolled_ed < swap_end_date:
        # non_rolled_ed = swap_freq.apply(non_rolled_ed, FinCalendar.none, BIZDAY_ROLL_RULE.NO_ROLL)
        non_rolled_ed = swap_freq.apply_no_roll(non_rolled_ed)
        rolled_ed = RDate.roll_to_bizday(non_rolled_ed, cal, roll_rule)
        end_dates.append(rolled_ed)

    swap_num_periods = len(end_dates)
    start_dates = [swap_start_date, *end_dates[:-1]]
    pay_dates   = [ pay_delay.apply(ed, cal, roll_rule) for ed in end_dates ]
    print(f'start dates: {start_dates}\nend dates  : {end_dates}\npay dates  : {pay_dates}')
    assert start_dates == sq.start_dates, f'{start_dates} != {sq.start_dates}'
    assert end_dates   == sq.end_dates,   f'{end_dates}   != {sq.end_dates}'
    assert pay_dates   == sq.pay_dates,   f'{pay_dates}   != {sq.pay_dates}'

    incr_dcfs = [dc_conv(sd,ed) for sd,ed in zip(start_dates,end_dates, strict=True)]
    print(f'manual incremental dcfs = {incr_dcfs}')
    print(f'swap incremental dcfs = {sq.incremental_dc_fractions}')
    assert incr_dcfs == sq.incremental_dc_fractions, f'{incr_dcfs} != {sq.incremental_dc_fractions}'


    assert sq.annuity_calc(zrc) == sq.annuity_calc(zrc,5), 'annuity default num periods is off'

    for num in range(5):
        manual_ann = sum(dcf*df for dcf, df in zip(incr_dcfs[:num+1], zrc.discount_factors(pay_dates, today = md_basis['md_date'])[:num+1]))
        print(f'manual annuity for {num+1} periods: {manual_ann}')
        assert manual_ann == sq.annuity_calc(zrc,num+1)



