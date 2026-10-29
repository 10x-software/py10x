from datetime import date

from cxxfin import bootstrap_cash_deposit as _bootstrap_cd
from cxxfin import bootstrap_swap as _bootstrap_sw
from xxcommon.rdate import PROPAGATE_DATES, RDate

from xxfin.ir_compounding import COMPOUND_TRANSFORM, compounding_apply
from xxfin.root_solver import xtol


def solve_cash_deposit(zrc, start_date, end_date, quote, mc, today):
    int_dc    = zrc.dc_convention
    int_comp  = zrc.compounding
    quot_comp = zrc.quoting_compounding

    t_today_end  = int_dc(today, end_date)
    t_start_end  = mc.dc_convention(start_date, end_date)

    t_today_start = 0.0
    gap_frac      = -1.0
    r_fixed       = 0.0

    if start_date == today:
        acc_start = 1.0
    else:
        t_today_start  = int_dc(today, start_date)
        last_fixed_ord = zrc.bcurve.times[-1]
        start_ord      = start_date.toordinal()

        if start_ord > last_fixed_ord:
            #-- start_date isn't known yet: it interpolates (via the curve's own linear
            #-- interior interpolation) between the last fixed knot and end_date, the
            #-- point currently being solved, so acc_start is a function of x, not a constant.
            end_ord   = end_date.toordinal()
            r_fixed   = zrc.bcurve.values[-1]
            gap_frac  = (start_ord - last_fixed_ord) / (end_ord - last_fixed_ord)
            acc_start = 0.0
        else:
            r_start   = zrc.bcurve.value(start_date)
            acc_start = compounding_apply(int_comp, COMPOUND_TRANSFORM.RATE_TO_ACCRUAL, t_today_start, r_start)

    _bootstrap_cd(
        zrc.bcurve,
        today.toordinal(), end_date.toordinal(),
        acc_start, t_today_end, t_start_end,
        int_comp, quot_comp,
        quote, -1., 1., xtol,
        t_today_start, gap_frac, r_fixed,
    )


def solve_swap(zrc, spot_date, swap_tenor, quote, mc, today):
    int_dc   = zrc.dc_convention
    int_comp = zrc.compounding

    fixed_dc_convention = mc.fixed_leg_swap_dc_convention
    fixed_freq          = RDate(freq=mc.fixed_leg_swap_tenor_frequency, count=1)
    swap_freq           = RDate(freq=mc.tenor_frequency,                count=1)
    swap_calendar       = mc.calendar
    swap_roll_rule      = mc.roll_rule
    pay_calendar        = mc.settlement_calendar
    pay_roll_rule       = mc.roll_rule_to_settle
    pay_offset          = mc.settle_offset

    end_date = swap_tenor.apply(spot_date, swap_calendar, swap_roll_rule)
    last_pay = pay_offset.apply(end_date, pay_calendar, pay_roll_rule)
    # last_pay == fixed_pays[-1] for standard (non-stub) swaps

    #-- same periods as RateCurve.swap_rate_simple_compounding() / swap_float_leg_simple_compounding()
    fixed_starts, fixed_ends, fixed_pays = zrc.period_dates(
        spot_date, swap_tenor, fixed_freq, swap_calendar, swap_roll_rule,
        pay_offset, pay_calendar, pay_roll_rule,
        PROPAGATE_DATES.FORWARD, False,
    )
    if pay_offset.count:
        float_starts, float_ends, float_pays = zrc.period_dates(
            spot_date, swap_tenor, swap_freq, swap_calendar, swap_roll_rule,
            pay_offset, pay_calendar, pay_roll_rule,
            PROPAGATE_DATES.FORWARD, False,
        )
    else:
        #-- telescoped float leg df(spot) - df(last_pay), as one period: (df(spot) / df(last_pay) - 1) * df(last_pay)
        float_starts, float_ends, float_pays = [spot_date], [last_pay], [last_pay]

    last_pay_ord   = last_pay.toordinal()
    last_fixed_ord = zrc.bcurve.times[-1]
    r_fixed        = zrc.bcurve.values[-1]

    def depends_on_x(d: date) -> bool:
        return d.toordinal() > last_fixed_ord or d == last_pay

    #-- nodes: dates whose discount factors are needed by the terms that depend on x
    node_by_date = {}
    node_t_todays, node_fracs, node_dfs = [], [], []

    def node(d: date) -> int:
        j = node_by_date.get(d)
        if j is not None:
            return j

        j = node_by_date[d] = len(node_fracs)
        d_ord = d.toordinal()
        if d == last_pay:
            frac = 1.
        elif d_ord > last_fixed_ord:
            #-- this date isn't known yet: it interpolates (via the curve's own linear interior
            #-- interpolation) between the last fixed knot and last_pay, the point currently being
            #-- solved, so its discount factor is a function of x, not a constant
            assert d_ord < last_pay_ord, f'{d} is beyond the swap last pay date {last_pay}'
            frac = (d_ord - last_fixed_ord) / (last_pay_ord - last_fixed_ord)
        else:
            frac = -1.

        node_fracs.append(frac)
        node_t_todays.append(int_dc(today, d) if frac >= 0. else 0.)
        node_dfs.append(zrc.discount_factor(d, today) if frac < 0. else 0.)
        return j

    annuity_const = 0.0
    fixed_dc_fracs, fixed_pay_nodes = [], []
    for start, end, pay in zip(fixed_starts, fixed_ends, fixed_pays, strict=True):
        dc_frac = fixed_dc_convention(start, end)
        if depends_on_x(pay):
            fixed_dc_fracs.append(dc_frac)
            fixed_pay_nodes.append(node(pay))
        else:
            annuity_const += dc_frac * zrc.discount_factor(pay, today)

    float_const = 0.0
    float_start_nodes, float_end_nodes, float_pay_nodes = [], [], []
    for start, end, pay in zip(float_starts, float_ends, float_pays, strict=True):
        if depends_on_x(start) or depends_on_x(end) or depends_on_x(pay):
            float_start_nodes.append(node(start))
            float_end_nodes.append(  node(end))
            float_pay_nodes.append(  node(pay))
        else:
            float_const += (zrc.discount_factor(start, today) / zrc.discount_factor(end, today) - 1.) * zrc.discount_factor(pay, today)

    bracket = (quote / 2., min(1., quote * 2.))

    _bootstrap_sw(
        zrc.bcurve,
        today.toordinal(), last_pay_ord,
        annuity_const, float_const,
        int_comp,
        quote, bracket[0], bracket[1], xtol,
        node_t_todays, node_fracs, node_dfs, r_fixed,
        fixed_dc_fracs, fixed_pay_nodes,
        float_start_nodes, float_end_nodes, float_pay_nodes,
    )
