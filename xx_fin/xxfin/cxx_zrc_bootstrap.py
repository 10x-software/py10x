from datetime import date

from cxxfin import bootstrap_cash_deposit as _bootstrap_cd
from cxxfin import bootstrap_swap as _bootstrap_sw

from xxfin.ir_compounding import COMPOUND_TRANSFORM, compounding_apply
from xxfin import root_solver
from xxfin.root_solver import xtol


def _last_fixed_knot(zrc, today: date) -> tuple:
    """
    (ordinal, rate) of the last already-bootstrapped knot.
    An empty curve has none yet: the beginning of time (today) is the knot to interpolate from,
    and the C++ solver anchors its rate at the trial value x (r_fixed is ignored then)
    """
    bcurve = zrc.bcurve
    if not bcurve.size:
        return today.toordinal(), 0.
    return bcurve.times[-1], bcurve.values[-1]


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
        last_fixed_ord, r_fixed = _last_fixed_knot(zrc, today)
        start_ord      = start_date.toordinal()

        if start_ord > last_fixed_ord:
            #-- start_date isn't known yet: it interpolates (via the curve's own linear
            #-- interior interpolation) between the last fixed knot and end_date, the
            #-- point currently being solved, so acc_start is a function of x, not a constant.
            end_ord   = end_date.toordinal()
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


def solve_swap(zrc, quotable, mc, today):
    int_dc   = zrc.dc_convention
    int_comp = zrc.compounding
    quote    = quotable.quote

    #-- the swap legs' schedules: the same periods as RateCurve.swap_rate_for_period_dates()
    fixed_dc_fractions = quotable.fixed_dc_fractions
    fixed_pays         = quotable.fixed_pay_dates
    float_starts       = quotable.start_dates
    float_ends         = quotable.end_dates
    float_pays         = quotable.pay_dates
    last_pay           = quotable.pay_date     # == fixed_pays[-1] == float_pays[-1]

    if float_pays == float_ends:
        #-- no pay delay: telescoped float leg df(spot) - df(last_pay), as one period: (df(spot) / df(last_pay) - 1) * df(last_pay)
        float_starts, float_ends, float_pays = [quotable.start_date], [last_pay], [last_pay]

    last_pay_ord   = last_pay.toordinal()
    last_fixed_ord, r_fixed = _last_fixed_knot(zrc, today)

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
    for dc_frac, pay in zip(fixed_dc_fractions, fixed_pays, strict=True):
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

    def bootstrap(lo: float, hi: float):
        _bootstrap_sw(
            zrc.bcurve,
            today.toordinal(), last_pay_ord,
            annuity_const, float_const,
            int_comp,
            quote, lo, hi, xtol,
            node_t_todays, node_fracs, node_dfs, r_fixed,
            fixed_dc_fracs, fixed_pay_nodes,
            float_start_nodes, float_end_nodes, float_pay_nodes,
        )

    #-- same as root_solver.ir_add_curve_point_near(): the narrow bracket around the quote 1st,
    #   the wide one only if the narrow one doesn't straddle the root (brent_solve throws then)
    try:
        bootstrap(quote - root_solver.near_half_width, quote + root_solver.near_half_width)
    except RuntimeError:
        bootstrap(-1., 1.)
