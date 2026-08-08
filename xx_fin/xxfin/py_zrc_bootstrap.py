from xxcommon.rdate import PROPAGATE_DATES, RDate

from xxfin.root_solver import ir_add_curve_point, xtol


def solve_cash_deposit(zrc, start_date, end_date, quote, mc, today):
    dc_convention = mc.dc_convention
    compounding   = mc.compounding
    bracket       = (-1., 1.)

    def f(x):
        zrc.update(end_date, x)
        if len(zrc.dates) < 3:
            zrc.update(zrc.beginning_of_time_as_date(), x)
        return zrc.rate_fwd(start_date, end_date, dc_convention, compounding) - quote

    rc = ir_add_curve_point(f, bracket, xtol)
    if not rc:
        raise ValueError(f'Failed to bootstrap cash deposit [{start_date} -> {end_date}]; {rc.error}')


def solve_swap(zrc, spot_date, swap_tenor, quote, mc, today):
    fixed_dc_convention = mc.fixed_leg_swap_dc_convention
    fixed_freq          = RDate(freq=mc.fixed_leg_swap_tenor_frequency, count=1)
    swap_calendar       = mc.calendar
    swap_roll_rule      = mc.roll_rule
    pay_calendar        = mc.settlement_calendar
    pay_roll_rule       = mc.roll_rule_to_settle
    pay_offset          = mc.settle_offset

    end_date = swap_tenor.apply(spot_date, swap_calendar, swap_roll_rule)
    last_pay = pay_offset.apply(end_date, pay_calendar, pay_roll_rule)
    bracket  = (quote / 2., min(1., quote * 2.))

    def f(x):
        zrc.update(last_pay, x)
        if len(zrc.dates) < 3:
            zrc.update(zrc.beginning_of_time_as_date(), x)
        return zrc.swap_rate_simple_compounding(
            spot_date, swap_tenor,
            fixed_freq, fixed_dc_convention, swap_calendar, swap_roll_rule,
            pay_offset, pay_calendar, pay_roll_rule,
            PROPAGATE_DATES.FORWARD, False, today
        ) - quote

    rc = ir_add_curve_point(f, bracket, xtol)
    if not rc:
        raise ValueError(f'Failed to bootstrap swap tenor={swap_tenor.symbol()}; {rc.error}')
