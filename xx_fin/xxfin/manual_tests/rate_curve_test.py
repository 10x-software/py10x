from datetime import date
from math import exp

from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate

from xxfin.fin_calendar import FinCalendar
from xxfin.py_day_count_convention import DAY_COUNT_CONVENTION
from xxfin.py_ir_compounding import COMPOUND_TRANSFORM, COMPOUNDING, compounding_apply

if __name__ == '__main__':

    from xxfin.py_rate_curve import RateCurve


    TEST_FXD_RATE       = True
    TEST__TODAY         = True
    TEST__CONVENTIONS   = True
    TEST_ACCRUAL        = True
    TEST_ACCRUAL_FWD    = True
    TEST_RATE_TO_INTERNAL= True
    TEST_ANNUITY        = True

    eps = 1.e-10

    # fmt: off
    c = RateCurve(
        dates   = [date(2019, 12, 31),    date(2020, 12, 31)  ],
        values  = [0.10,                0.20                ]
    )
    c.beginning_of_time = date(2019, 12, 1)
    # fmt: on


    additive_dcs = [
        DAY_COUNT_CONVENTION.ACT360,
        DAY_COUNT_CONVENTION.ACT365,
        DAY_COUNT_CONVENTION.ACTACT,
    ]

    none_additive_dcs = [
        DAY_COUNT_CONVENTION.US30360,
        DAY_COUNT_CONVENTION.BB30360,
        DAY_COUNT_CONVENTION.EB30360,
    ]

    all_dcs = additive_dcs + none_additive_dcs

    cmps = [
        COMPOUNDING.SIMPLE,
        COMPOUNDING.ANNUAL,
        COMPOUNDING.SEMI_ANNUAL,
        COMPOUNDING.CONTINUOUS,
    ]

    dd_2028_decdec = [date(2027,12,31), date(2028,12,31)]
    dd_2028_janjan = [date(2028,1,1),   date(2029,1,1)  ]
    dd_2028_janfeb = [date(2028,1,31),  date(2028,2,29) ]
    some_periods = [dd_2028_janjan, dd_2028_janjan, dd_2028_janfeb]

    some_dates = [
        date(2028, 1, 1),
        date(2029, 1, 1),
        date(2039, 1, 1),
        date(2049, 1, 1),
    ]

    #test fixed_rate_acc()
    if TEST_FXD_RATE:
        r = 0.1
        for d1, d2 in some_periods:
            for dc in additive_dcs:
                for cmp in cmps:
                    t = dc(d1, d2)
                    acc = compounding_apply(cmp, COMPOUND_TRANSFORM.RATE_TO_ACCRUAL, t, r)
                    print(f'dates: {d1} - {d2}, dc = {dc}, compund =  {cmp}: dcf = {t}, accrual = {acc}')
                    assert c.fixed_rate_accrual(r, d1, d1, dc, cmp) == 1.
                    print('checked same start/end')
                    assert c.fixed_rate_accrual(r, d1, d2, dc, cmp) == acc
                    assert c.fixed_rate_accrual(r, d2, d1, dc, cmp) == acc
                    print('checked reversed start/end\n')

    # test _today()
    if TEST__TODAY:
        bot = c.beginning_of_time_as_date()
        d = date(2028,1,1)
        assert c._today(None) == bot
        print(f'None --> bot = {bot}')
        # c.beginning_of_time = None
        ## assertRaise(ValueError...)
        # c.beginning_of_time = bot
        assert c._today(d) == d
        print(f'non-None {d} returns itself ')

    if TEST__CONVENTIONS:
        # set conventions diff from internal
        dc  = DAY_COUNT_CONVENTION.ACT365
        cmp = COMPOUNDING.ANNUAL
        print(f'given dc/comp = {dc}/{cmp}')
        cdc  = c.quoting_dc_convention
        ccmp = c.quoting_compounding
        print(f'internal dc/comp = {cdc}/{ccmp}')
        inp = [(None, None), (dc, None), (None, cmp), (dc, cmp)]
        out = [(cdc,  ccmp), (dc, ccmp), (cdc,  cmp), (dc, cmp)]
        for i,o in zip(inp, out):
            output = c._conventions(*i)
            print(f'input = {i}\n  exp output = {o}\n  act output = {output}')
            assert output == o

    if TEST_ACCRUAL:
        (d,r) = c.dates_values()[-1]
        assert c.value(d) == r

        save_dc  = c.dc_convention
        save_cmp = c.compounding

        dc_cmps = [
            (DAY_COUNT_CONVENTION.ACT360,   COMPOUNDING.CONTINUOUS, lambda t, r: exp(r*t)),
            (DAY_COUNT_CONVENTION.ACT365,   COMPOUNDING.SIMPLE,     lambda t, r: (1+r*t)),
            (DAY_COUNT_CONVENTION.US30360,  COMPOUNDING.ANNUAL,     lambda t, r: (1+r)**t),
        ]
        today = c.beginning_of_time_as_date()
        for dc, cmp, fn in dc_cmps:
            acc = fn(dc(today, d), r)
            c.dc_convention = dc
            c.compounding   = cmp
            act_acc = c.accrual(d)
            print(f'{d}: {dc}/{cmp} manual accrual = {acc}, calc acc = {act_acc}')
            assert acc == act_acc

    if TEST_ACCRUAL_FWD:
        ...

    if TEST_RATE_TO_INTERNAL:
        d1 = date(2028, 1, 1)
        d2 = date(2029, 1, 1)
        bot = c.beginning_of_time_as_date()
        r_init = 0.25
        # dc  = DAY_COUNT_CONVENTION.ACT360
        dc  = DAY_COUNT_CONVENTION.BB30360
        # cmp = COMPOUNDING.CONTINUOUS
        cmp = COMPOUNDING.MONTHLY
        cmp = COMPOUNDING.SIMPLE
        print(f'dc = {dc} / comp = {cmp} --> {c.dc_convention}/{c.compounding}')
        r = c.rate_convert(r_init, bot, d2, dc, cmp, c.dc_convention, c.compounding)[0]
        ri = c.rate_to_internal(r_init, d2, dc, cmp, bot)
        print(f'internal dc/comp = {c.dc_convention}/{c.compounding}')
        print(f'external dc/comp = {dc}/{cmp}')
        print(f'ri = {ri}, r converted = {r}')


    if TEST_ANNUITY:
        save_values = c.values
        c.values = [0] * len(save_values)

        # tenor           = RDate('5Y')
        # period_freq     = RDate('1Q')
        period_cal      = FinCalendar.none,
        period_roll_rule= BIZDAY_ROLL_RULE.NO_ROLL
        pay_delay       = RDate('0C')
        pay_calendar    = FinCalendar.none
        pay_roll_rule   = BIZDAY_ROLL_RULE.NO_ROLL

        for tenor in [ RDate('1Y'), RDate('5Y')]:
            for period_freq in [ RDate('1M'), RDate('1Q'), RDate('1S'), RDate('1Y')]:
                for dc in all_dcs:
                # for dc in additive_dcs:
                    for start in some_dates:
                        ann = c.annuity(dc, start, tenor,
                                              period_freq, period_cal, period_roll_rule,
                                              pay_delay, pay_calendar, pay_roll_rule,
                                              ## add the rest of the defaults later
                                              )
                        end = tenor.apply(start, period_cal, period_roll_rule)
                        full_dcf = dc(start, end)
                        print(f'dc = {dc}, start/end = {start}/{end}, tenor/period freq = {tenor}/{period_freq}, ann = {ann}, full dcf = {full_dcf}')
                        assert  abs(ann - full_dcf) < eps

        c.values = save_values

    #test defaults




    # c.dc_convention = DAY_COUNT_CONVENTION.ACT365
    # c.compounding   = COMPOUNDING.SIMPLE

