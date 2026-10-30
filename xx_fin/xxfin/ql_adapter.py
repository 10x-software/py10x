from datetime import date

import QuantLib as ql
from xxcommon.rdate import BIZDAY_ROLL_RULE, TENOR_FREQUENCY, RDate

from xxfin.day_count_convention import DAY_COUNT_CONVENTION
from xxfin.ir_cash_deposit_quotable import IRCashDepositQuotable
from xxfin.ir_compounding import COMPOUNDING
from xxfin.ir_rate_mkt_conventions import IRRateMktConventions
from xxfin.ir_swap_quotable import IRSwapQuotable


class QL:
    """
    Adapter converting native 10x/xxfin conventions into their QuantLib equivalents.
    """

    s_day_counter = {
        DAY_COUNT_CONVENTION.ACT360:    ql.Actual360,
        DAY_COUNT_CONVENTION.ACT365:    ql.Actual365Fixed,
        DAY_COUNT_CONVENTION.ACTACT:    lambda: ql.ActualActual(ql.ActualActual.ISDA),
        DAY_COUNT_CONVENTION.BB30360:   lambda: ql.Thirty360(ql.Thirty360.BondBasis),
        DAY_COUNT_CONVENTION.US30360:   lambda: ql.Thirty360(ql.Thirty360.USA),
        DAY_COUNT_CONVENTION.EB30360:   lambda: ql.Thirty360(ql.Thirty360.European),
    }

    s_business_day_convention = {
        BIZDAY_ROLL_RULE.FOLLOWING:     ql.Following,
        BIZDAY_ROLL_RULE.PRECEDING:     ql.Preceding,
        BIZDAY_ROLL_RULE.MOD_FOLLOWING: ql.ModifiedFollowing,
        BIZDAY_ROLL_RULE.MOD_PRECEDING: ql.ModifiedPreceding,
        BIZDAY_ROLL_RULE.NO_ROLL:       ql.Unadjusted,
    }

    #-- RDate.symbol() (e.g. '1S' for half-year, '1Q' for quarter) does not match ql.Period's own
    #   string grammar, so tenors are converted via RDate.freq/count -> ql.Period(count, TimeUnit)
    #   directly rather than by parsing a string.
    #   BIZDAY -> ql.Days is exact for any count, not only 1. ql.Period(n, ql.Days) advances
    #   n business days (weekends and holidays are skipped) -- the same advance deposit_helper
    #   relies on -- so an overnight '1B' and a longer 'nB' are both business-day tenors.
    s_time_unit = {
        TENOR_FREQUENCY.BIZDAY:     (ql.Days,   1),
        TENOR_FREQUENCY.WEEK:       (ql.Weeks,  1),
        TENOR_FREQUENCY.MONTH:      (ql.Months, 1),
        TENOR_FREQUENCY.QUARTER:    (ql.Months, 3),
        TENOR_FREQUENCY.HALF_YEAR:  (ql.Months, 6),
        TENOR_FREQUENCY.YEAR:       (ql.Months, 12),
    }

    #-- (ql compounding, ql frequency) -- frequency is meaningless for SIMPLE/CONTINUOUS but ql's
    #   InterestRate/zeroRate() APIs require one to be passed regardless
    s_compounding = {
        COMPOUNDING.SIMPLE:         (ql.Simple,     ql.NoFrequency),
        COMPOUNDING.CONTINUOUS:     (ql.Continuous, ql.NoFrequency),
        COMPOUNDING.ANNUAL:         (ql.Compounded, ql.Annual),
        COMPOUNDING.SEMI_ANNUAL:    (ql.Compounded, ql.Semiannual),
        COMPOUNDING.QUARTERLY:      (ql.Compounded, ql.Quarterly),
        COMPOUNDING.MONTHLY:        (ql.Compounded, ql.Monthly),
        COMPOUNDING.WEEKLY:         (ql.Compounded, ql.Weekly),
    }

    s_frequency = {
        TENOR_FREQUENCY.WEEK:       ql.Weekly,
        TENOR_FREQUENCY.MONTH:      ql.Monthly,
        TENOR_FREQUENCY.QUARTER:    ql.Quarterly,
        TENOR_FREQUENCY.HALF_YEAR:  ql.Semiannual,
        TENOR_FREQUENCY.YEAR:       ql.Annual,
    }

    #-- named ql.Currency subclasses only cover the currencies real xxfin OIS markets quote in
    #   today (SOFR/USD, SONIA/GBP, CORRA/CAD); extend as new markets need it
    s_currency = {
        'USD':  ql.USDCurrency,
        'GBP':  ql.GBPCurrency,
        'CAD':  ql.CADCurrency,
        'EUR':  ql.EURCurrency,
        'JPY':  ql.JPYCurrency,
    }

    @classmethod
    def to_date(cls, d: date) -> ql.Date:
        return ql.Date(d.day, d.month, d.year)

    @classmethod
    def day_counter(cls, dc_convention: DAY_COUNT_CONVENTION) -> ql.DayCounter:
        f = cls.s_day_counter.get(dc_convention)
        if f is None:
            raise ValueError(f'No ql DayCounter mapping for {dc_convention}')
        return f()

    @classmethod
    def business_day_convention(cls, roll_rule: BIZDAY_ROLL_RULE) -> int:
        bdc = cls.s_business_day_convention.get(roll_rule)
        if bdc is None:
            raise ValueError(f'No ql BusinessDayConvention mapping for {roll_rule}')
        return bdc

    @classmethod
    def compounding(cls, comp: COMPOUNDING) -> tuple[int, int]:
        pair = cls.s_compounding.get(comp)
        if pair is None:
            raise ValueError(f'No ql Compounding mapping for {comp}')
        return pair

    @classmethod
    def period(cls, tenor: RDate) -> ql.Period:
        unit_info = cls.s_time_unit.get(tenor.freq)
        if unit_info is None:
            raise ValueError(f'No ql Period mapping for tenor frequency {tenor.freq}')
        unit, multiplier = unit_info
        return ql.Period(tenor.count * multiplier, unit)

    @classmethod
    def frequency(cls, tenor_freq: TENOR_FREQUENCY) -> int:
        freq = cls.s_frequency.get(tenor_freq)
        if freq is None:
            raise ValueError(f'No ql Frequency mapping for tenor frequency {tenor_freq}')
        return freq

    @classmethod
    def currency(cls, ccy_name: str) -> ql.Currency:
        f = cls.s_currency.get(ccy_name)
        if f is None:
            raise ValueError(f'No ql Currency mapping for {ccy_name}')
        return f()

    @classmethod
    def overnight_index(cls, mc: IRRateMktConventions, forecast_curve: ql.RelinkableYieldTermStructureHandle) -> ql.OvernightIndex:
        #-- fixing days stay 0. A nonzero OvernightIndex settlement day is a lookback on each
        #   overnight fixing, not the swap spot lag (that is an OISRateHelper argument).
        return ql.OvernightIndex(
            mc.mkt_name,
            0,
            cls.currency(mc.ccy.name),
            mc.calendar.ql_calendar,
            cls.day_counter(mc.dc_convention),
            forecast_curve,
        )

    @classmethod
    def deposit_helper(cls, quotable: IRCashDepositQuotable, mc: IRRateMktConventions, md_date: date) -> ql.DepositRateHelper:
        #-- Spot deposits (every tenor but '1B') start on the spot date rolled on the currency
        #   bank calendar, not mc.calendar. The helper then advances fixingDays on the calendar
        #   it is given, so that calendar has to be the one that produced start_date or the
        #   start misses it. USD bank calendar FD and the SOFR curve calendar US differ inside
        #   T+2. '1B' starts today and its end rolls on mc.calendar; keep that calendar so the
        #   overnight business-day advance does not move onto the bank calendar.
        if quotable.tenor.symbol() == '1B':
            calendar = mc.calendar.ql_calendar
        else:
            calendar = mc.ccy.bank_calendar.ql_calendar
        fixing_days = calendar.businessDaysBetween(cls.to_date(md_date), cls.to_date(quotable.start_date))

        return ql.DepositRateHelper(
            ql.QuoteHandle(ql.SimpleQuote(quotable.quote)),
            cls.period(quotable.tenor),
            fixing_days,
            calendar,
            cls.business_day_convention(mc.roll_rule),
            False,
            cls.day_counter(mc.dc_convention),
        )

    @classmethod
    def swap_helper(cls, quotable: IRSwapQuotable, mc: IRRateMktConventions, index: ql.OvernightIndex) -> ql.OISRateHelper:
        #-- ql.OISRateHelper has no separate fixed-leg day counter parameter -- it reprices the
        #   fixed leg using the overnight index's own day counter (mc.dc_convention). The native
        #   swap_rate_simple_compounding() supports an independent fixed_leg_swap_dc_convention,
        #   but every real market defined so far has fixed == float day count, so this is not
        #   exercised in practice; raise loudly rather than silently mispricing if that ever changes.
        if mc.fixed_leg_swap_dc_convention is not mc.dc_convention:
            raise NotImplementedError(f'{mc.mkt_name}: OISRateHelper cannot express a fixed-leg day count ({mc.fixed_leg_swap_dc_convention}) different from the index day count ({mc.dc_convention})')

        #-- settlementDays is a business-day spot lag. A week or month count is not that lag.
        if mc.spot_offset.freq is not TENOR_FREQUENCY.BIZDAY:
            raise ValueError(f'{mc.mkt_name}: OIS spot lag must be business days, got {mc.spot_offset.symbol()}')

        payment_frequency = cls.frequency(mc.fixed_leg_swap_tenor_frequency)

        return ql.OISRateHelper(
            mc.spot_offset.count,
            cls.period(quotable.tenor),
            quotable.quote,
            index,
            paymentLag           = mc.settle_offset.count,
            paymentConvention    = cls.business_day_convention(mc.roll_rule_to_settle),
            paymentFrequency     = payment_frequency,
            paymentCalendar      = mc.settlement_calendar.ql_calendar,
            averagingMethod      = ql.RateAveraging.Compound,
            fixedPaymentFrequency = payment_frequency,
            fixedCalendar        = mc.calendar.ql_calendar,
            convention           = cls.business_day_convention(mc.roll_rule),
            #-- native solve_swap propagates FORWARD with no end-of-month rule. The helper
            #   default is Backward, and an omitted endOfMonth turns on at month-end starts.
            rule                 = ql.DateGeneration.Forward,
            endOfMonth           = False,
        )

