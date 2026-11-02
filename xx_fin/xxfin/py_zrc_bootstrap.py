from xxfin.root_solver import ir_add_curve_point, ir_add_curve_point_near, xtol


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


def solve_swap(zrc, quotable, mc, today):
    #-- the schedules don't depend on the root x: take them from the quotable (computed once, not per iteration)
    fixed_dc_fractions = quotable.fixed_dc_fractions
    fixed_pays         = quotable.fixed_pay_dates
    float_starts       = quotable.start_dates
    float_ends         = quotable.end_dates
    float_pays         = quotable.pay_dates
    last_pay           = quotable.pay_date
    quote              = quotable.quote

    def f(x):
        zrc.update(last_pay, x)
        if len(zrc.dates) < 3:
            zrc.update(zrc.beginning_of_time_as_date(), x)
        return zrc.swap_rate_for_period_dates(fixed_dc_fractions, fixed_pays, float_starts, float_ends, float_pays, today) - quote

    #-- the zero rate x at the swap's last pay date is close to the swap rate quote
    rc = ir_add_curve_point_near(f, quote, xtol)
    if not rc:
        raise ValueError(f'Failed to bootstrap swap tenor={quotable.tenor.symbol()}; {rc.error}')
