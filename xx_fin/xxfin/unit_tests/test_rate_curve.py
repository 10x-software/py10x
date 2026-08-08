from datetime import date
from math import exp, log

import pytest
from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate

from xxfin.fin_calendar import FinCalendar

COMPOUNDING = None
COMPOUND_TRANSFORM = None
compounding_apply = None
DAY_COUNT_CONVENTION = None
RateCurve = None

@pytest.fixture(autouse=True)
def rebind_globals(cxx_or_py_rates_curve):
    global COMPOUNDING, COMPOUND_TRANSFORM, compounding_apply, DAY_COUNT_CONVENTION, RateCurve
    from xxfin.day_count_convention import DAY_COUNT_CONVENTION
    from xxfin.ir_compounding import COMPOUND_TRANSFORM, COMPOUNDING, compounding_apply
    from xxfin.rate_curve import RateCurve
    yield

class TestRateCurve:
    def setup_method(self):
        self.rc = RateCurve(
            dates   = [date(2020, 1, 1), date(2020, 12, 31)],
            values  = [0.10, 0.20]
        )
        self.rc.beginning_of_time = date(2019, 12, 1)

        self.additive_dcs = [
            DAY_COUNT_CONVENTION.ACT360,
            DAY_COUNT_CONVENTION.ACT365,
            DAY_COUNT_CONVENTION.ACTACT,
        ]

        self.none_additive_dcs = [
            DAY_COUNT_CONVENTION.US30360,
            DAY_COUNT_CONVENTION.BB30360,
            DAY_COUNT_CONVENTION.EB30360,
        ]

        self.all_dcs = self.additive_dcs + self.none_additive_dcs

        self.cmps = [
            COMPOUNDING.SIMPLE,
            COMPOUNDING.ANNUAL,
            COMPOUNDING.SEMI_ANNUAL,
            COMPOUNDING.CONTINUOUS,
        ]

        self.dd_2028_decdec = [date(2027, 12, 31), date(2028, 12, 31)]
        self.dd_2028_janjan = [date(2028, 1, 1), date(2029, 1, 1)]
        self.dd_2028_janfeb = [date(2028, 1, 31), date(2028, 2, 29)]
        self.some_periods = [self.dd_2028_janjan, self.dd_2028_janjan, self.dd_2028_janfeb]

        self.some_dates = [
            date(2028, 1, 1),
            date(2029, 1, 1),
            date(2039, 1, 1),
            date(2049, 1, 1),
        ]

        self.dc_cmps_rTOa_aTOr = [
            (DAY_COUNT_CONVENTION.ACT360,   COMPOUNDING.CONTINUOUS, lambda t, r: exp(r*t), lambda t, a: log(a)/t ),
            (DAY_COUNT_CONVENTION.ACT365,   COMPOUNDING.SIMPLE,     lambda t, r: (1+r*t),  lambda t, a: (a-1.)/t ),
            (DAY_COUNT_CONVENTION.US30360,  COMPOUNDING.ANNUAL,     lambda t, r: (1+r)**t,          lambda t, a: (a**(1./t)) - 1. ),
        ]

    def test_fixed_rate_accrual(self):
        r = 0.1
        for d1, d2 in self.some_periods:
            for dc in self.additive_dcs:
                for cmp in self.cmps:
                    t = dc(d1, d2)
                    acc = compounding_apply(cmp, COMPOUND_TRANSFORM.RATE_TO_ACCRUAL, t, r)
                    assert self.rc.fixed_rate_accrual(r, d1, d1, dc, cmp) == 1.
                    assert self.rc.fixed_rate_accrual(r, d1, d2, dc, cmp) == acc
                    assert self.rc.fixed_rate_accrual(r, d2, d1, dc, cmp) == acc

    def test__today(self):
        bot = self.rc.beginning_of_time_as_date()
        d = date(2028, 1, 1)
        assert self.rc._today(None) == bot
        assert self.rc._today(d) == d

    def test__conventions(self):
        dc = DAY_COUNT_CONVENTION.ACT365
        cmp = COMPOUNDING.ANNUAL
        cdc = self.rc.quoting_dc_convention
        ccmp = self.rc.quoting_compounding
        inp = [(None, None), (dc, None), (None, cmp), (dc, cmp)]
        out = [(cdc,  ccmp), (dc, ccmp), (cdc,  cmp), (dc, cmp)]
        for i, o in zip(inp, out, strict=False):
            assert self.rc._conventions(*i) == o

    def test_accrual_1(self):
        d = date(2028, 1, 1)
        assert self.rc.accrual(d,d) == 1.
        assert self.rc.accrual(self.rc.beginning_of_time_as_date()) == 1.

    def test_accrual(self):
        (d,r) = self.rc.dates_values()[-1]
        assert self.rc.value(d) == r

        ## TODO: need cache layer instead of manual save/restore
        save_dc  = self.rc.dc_convention
        save_cmp = self.rc.compounding

        today = self.rc.beginning_of_time_as_date()
        for dc, cmp, fn, _ in self.dc_cmps_rTOa_aTOr:
            acc = fn(dc(today, d), r)
            self.rc.dc_convention = dc
            self.rc.compounding   = cmp
            act_acc = self.rc.accrual(d)
            assert acc == act_acc

        self.rc.dc_convention = save_dc
        self.rc.compounding   = save_cmp

    def test_accrual_fwd_1(self):
        d = self.some_dates[0]
        assert self.rc.accrual_fwd(d, d) == 1.
        assert self.rc.accrual_fwd(d, d, self.rc.beginning_of_time_as_date()) == 1.

    def test_accrual_fwd(self):
        d1, d2 = self.some_dates[:2]

        assert self.rc.accrual_fwd(d1, d2) == self.rc.accrual_fwd(d2, d1)
        assert self.rc.accrual_fwd(d1, d2) == self.rc.accrual(d2)/self.rc.accrual(d1)

        d = self.some_dates[0]
        assert self.rc.accrual_fwd(d1, d2, d) == self.rc.accrual(d2, d)/self.rc.accrual(d1, d)
        assert self.rc.accrual_fwd(d1, d2, d) != self.rc.accrual_fwd(d1, d2)

    def test_rate_def_parm(self):
        d = self.some_dates[0]
        r = self.rc.rate(d)
        assert self.rc.rate(d, self.rc.quoting_dc_convention, self.rc.quoting_compounding, self.rc.beginning_of_time_as_date()) == r

    def test_rate(self):
        d0 = self.some_dates[0]
        a0 = self.rc.accrual(d0)
        bot = self.rc.beginning_of_time_as_date()
        for dc, cmp, _, fn in self.dc_cmps_rTOa_aTOr:
            t = dc(bot, d0)
            r = self.rc.rate(d0, dc, cmp, bot)
            assert r == fn(t, a0)

    def test_rate_fwd_def_parm(self):
        d1 = date(2028, 1, 1)
        d2 = date(2029, 1, 1)
        r  = self.rc.rate_fwd(d1, d2)
        assert self.rc.rate_fwd(d1, d2, self.rc.quoting_dc_convention, self.rc.quoting_compounding, self.rc.beginning_of_time_as_date()) == r
        assert self.rc.rate_fwd(d2, d1) == r

    def test_rate_fwd(self):
        d1, d2 = self.some_dates[:2]
        bot = self.rc.beginning_of_time_as_date()
        # r12 = self.rc.rate_fwd(d1, d2, today = bot)
        a12 = self.rc.accrual(d2, today = bot) / self.rc.accrual(d1, today = bot)
        for dc, cmp, _, fn in self.dc_cmps_rTOa_aTOr:
            t = dc(d1, d2)
            r = self.rc.rate_fwd(d1, d2, dc, cmp, bot)
            assert r == fn(t, a12)

    def test_rate_from_accrual(self):
        d = self.some_dates[0]
        bot = self.rc.beginning_of_time_as_date()
        a = 1.5
        for dc, cmp, _, fn in self.dc_cmps_rTOa_aTOr:
            t = dc(bot, d)
            r = self.rc.rate_from_accrual(d, a, dc, cmp, bot)
            assert r == fn(t, a)

    def test_rate_convert(self):
        d1, d2 = self.some_dates[:2]
        r_in = 0.25
        for dc_in, cmp_in, rate_to_acc, _ in self.dc_cmps_rTOa_aTOr:
            t_in = dc_in(d1, d2)
            acc = rate_to_acc(t_in, r_in)
            for dc_out, cmp_out, _, acc_to_rate in self.dc_cmps_rTOa_aTOr:
                t_out = dc_out(d1, d2)
                r_t_out = self.rc.rate_convert(r_in, d1, d2, dc_in, cmp_in, dc_out, cmp_out)
                assert r_t_out == (acc_to_rate(t_out, acc), t_out)

    def test_rate_convert_exp_const(self):
        r_in = 0.25
        exp_cmps = [ COMPOUNDING.CONTINUOUS, COMPOUNDING.ANNUAL, COMPOUNDING.SEMI_ANNUAL,COMPOUNDING.QUARTERLY, COMPOUNDING.MONTHLY]
        dc = DAY_COUNT_CONVENTION.BB30360
        dd = self.some_dates
        for cmp_in in exp_cmps:
            for cmp_out in exp_cmps:
                rr = [self.rc.rate_convert(r_in, dd[0], d, dc, cmp_in, dc, cmp_out)[0] for d in dd[1:]]
                for r in rr[1:]:
                    assert r == pytest.approx(rr[0])

    def test_rate_to_internal(self):
        _d1, d2 = self.some_dates[:2]
        bot = self.rc.beginning_of_time_as_date()
        r_init = 0.25
        dc  = DAY_COUNT_CONVENTION.BB30360
        cmp = COMPOUNDING.SIMPLE
        r = self.rc.rate_convert(r_init, bot, d2, dc, cmp, self.rc.dc_convention, self.rc.compounding)[0]
        assert self.rc.rate_to_internal(r_init, d2, dc, cmp, bot) == pytest.approx(r)

    def test_internal_rate_from_accrual(self):
        d1 = self.some_dates[0]
        r = 0.25
        t = self.rc.dc_convention(self.rc.beginning_of_time_as_date(), d1)
        acc = compounding_apply(self.rc.compounding, COMPOUND_TRANSFORM.RATE_TO_ACCRUAL, t, r)
        assert self.rc.internal_rate_from_accrual(d1, acc) == r

    def test_discount_factor(self):
        d = self.some_dates[0]
        assert self.rc.discount_factor(d,d) == 1.
        df  = self.rc.discount_factor(d)
        assert df == self.rc.discount_factor(d, self.rc.beginning_of_time_as_date())
        acc = self.rc.accrual(d)
        assert acc * df == pytest.approx(1.)

    def test_discount_factors_1(self):
        save_values = self.rc.values
        self.rc.values = [0] * len(save_values)
        assert self.rc.discount_factors(self.rc.dates) == [1.] * len(save_values)
        self.rc.values = save_values

    def test_discount_factors(self):
        assert self.rc.discount_factors(self.some_dates) == [self.rc.discount_factor(d) for d in self.some_dates]
        assert self.rc.discount_factors() == self.rc.discount_factors(self.rc.dates)

    def test_discount_factors_dates(self):
        assert self.rc.discount_factors_dates(self.some_dates) == [(d, self.rc.discount_factor(d)) for d in self.some_dates]
        assert self.rc.discount_factors_dates() == self.rc.discount_factors_dates(self.rc.dates)

    def test_discount_factors_fwd(self):
        for d1, d2 in self.some_periods:
            assert self.rc.accrual_fwd(d1, d2) * self.rc.discount_factor_fwd(d1, d2) == pytest.approx(1.)

    def test_annuity(self):
        save_values = self.rc.values
        self.rc.values = [0] * len(save_values)

        # tenor           = RDate('1Y')
        # period_freq     = RDate('1Q')
        period_cal      = FinCalendar.none
        period_roll_rule= BIZDAY_ROLL_RULE.NO_ROLL
        pay_delay       = RDate('0C')
        pay_calendar    = FinCalendar.none
        pay_roll_rule   = BIZDAY_ROLL_RULE.NO_ROLL

        for tenor in [ RDate('1Y'), RDate('5Y')]:
            for period_freq in [ RDate('1M'), RDate('1Q'), RDate('1S'), RDate('1Y')]:
                # for dc in self.additive_dcs:
                for dc in self.all_dcs:
                    for start in self.some_dates:
                        ann = self.rc.annuity(dc, start, tenor,
                                              period_freq, period_cal, period_roll_rule,
                                              pay_delay, pay_calendar, pay_roll_rule,
                                              ## add the rest of the defaults later
                                          )
                        end = tenor.apply(start, period_cal, period_roll_rule)
                        full_dcf = dc(start, end)
                        assert ann == pytest.approx(full_dcf)

        self.rc.values = save_values

    def test_swap_rate_simple(self):
        ## TODO: comp no-arb calc to the actual float leg /  annuity (i.e., float leg = 1-df_last)
        ...
