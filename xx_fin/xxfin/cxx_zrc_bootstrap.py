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
    swap_calendar       = mc.calendar
    swap_roll_rule      = mc.roll_rule
    pay_calendar        = mc.settlement_calendar
    pay_roll_rule       = mc.roll_rule_to_settle
    pay_offset          = mc.settle_offset

    start_dates, end_dates, _ = fixed_freq.period_dates_for_tenor(
        spot_date, swap_tenor, swap_calendar, swap_roll_rule,
        PROPAGATE_DATES.FORWARD, False,
    )
    pay_dates  = [pay_offset.apply(ed, pay_calendar, pay_roll_rule) for ed in end_dates]
    dc_fracs   = [fixed_dc_convention(s, e) for s, e in zip(start_dates, end_dates, strict=False)]

    end_date = swap_tenor.apply(spot_date, swap_calendar, swap_roll_rule)
    last_pay = pay_offset.apply(end_date, pay_calendar, pay_roll_rule)
    # last_pay == pay_dates[-1] for standard (non-stub) swaps

    t_today_last   = int_dc(today, last_pay)
    df_spot        = zrc.discount_factor(spot_date, today)
    last_pay_ord   = last_pay.toordinal()
    last_fixed_ord = zrc.bcurve.times[-1]
    r_fixed        = zrc.bcurve.values[-1]

    annuity_const = 0.0
    gap_dc_fracs, gap_t_todays, gap_fracs = [], [], []
    for i in range(len(pay_dates) - 1):
        pay_ord = pay_dates[i].toordinal()
        if pay_ord > last_fixed_ord:
            #-- this period's pay date isn't known yet: it interpolates (via the curve's
            #-- own linear interior interpolation) between the last fixed knot and
            #-- last_pay, the point currently being solved, so its discount factor is a
            #-- function of x, not a constant that can be folded into annuity_const.
            gap_dc_fracs.append(dc_fracs[i])
            gap_t_todays.append(int_dc(today, pay_dates[i]))
            gap_fracs.append((pay_ord - last_fixed_ord) / (last_pay_ord - last_fixed_ord))
        else:
            annuity_const += dc_fracs[i] * zrc.discount_factor(pay_dates[i], today)

    last_dc_frac  = dc_fracs[-1]
    bracket       = (quote / 2., min(1., quote * 2.))

    _bootstrap_sw(
        zrc.bcurve,
        today.toordinal(), last_pay_ord,
        t_today_last, annuity_const, last_dc_frac, df_spot,
        int_comp,
        quote, bracket[0], bracket[1], xtol,
        gap_dc_fracs, gap_t_todays, gap_fracs, r_fixed,
    )
