from __future__ import annotations

import math
import re
from datetime import date

from dateutil.relativedelta import relativedelta

from core_10x.named_constant import NamedConstant, NamedConstantTable
from core_10x.nucleus import Nucleus
from xx_common.xxcalendar import Calendar


# =====
#   Biz Day Roll Rules
#   1. Preceding (rolls backwards): go to the prev biz day, if not already
#   2. Following (rolls forward):   go to the next biz day, if not already
#   3. Modified following:          go to the next biz day unless the next biz day is in the next month, otherwise go to 1.
#   4. Modified preceding:          go to the prev biz day unless the prev biz day is in the prev month, otherwise go to 2.
# =====
def bizday_roll_preceding(d: date, cal: Calendar) -> date:
    if cal.is_bizday(d):
        return d

    return cal.prev_bizday(d)


def bizday_roll_following(d: date, cal: Calendar) -> date:
    if cal.is_bizday(d):
        return d

    return cal.next_bizday(d)


def bizday_roll_mod_following(d: date, cal: Calendar) -> date:
    if cal.is_bizday(d):
        return d

    res = cal.next_bizday(d)
    return res if res.month == d.month else cal.prev_bizday(d)


def bizday_roll_mod_preceding(d: date, cal: Calendar) -> date:
    if cal.is_bizday(d):
        return d

    res = cal.prev_bizday(d)
    return res if res.month == d.month else cal.next_bizday(d)


# fmt: off
class BIZDAY_ROLL_RULE(NamedConstant):
    PRECEDING       = bizday_roll_preceding
    FOLLOWING       = bizday_roll_following
    MOD_FOLLOWING   = bizday_roll_mod_following
    MOD_PRECEDING   = bizday_roll_mod_preceding
    NO_ROLL         = lambda d, cal: d

class TENOR_FREQUENCY(NamedConstant):
    BIZDAY      = ()
    CALDAY      = ()
    WEEK        = ()
    MONTH       = ()
    QUARTER     = ()
    HALF_YEAR   = ()
    YEAR        = ()
    SOM         = ()
    EOM         = ()
    #IMM_QUARTER = ()   # TODO - use later

class TENOR_PARAMS(NamedConstant):
    CHAR            = ()
    RELATIVE_DELTA  = ()
    CONVERSIONS     = ()
    MIN_FREQUENCY   = ()

FREQUENCY_TABLE = NamedConstantTable(TENOR_FREQUENCY, TENOR_PARAMS,
    #              CHAR         RELATIVE_DELTA                                      CONVERSIONS                                         MIN_FREQUENCY
    BIZDAY      = ('B',         None,                                               None,                                               None),
    CALDAY      = ('C',         lambda d, n: d + relativedelta(days    = n),        dict(C = 1,     W = 1/7),                           TENOR_FREQUENCY.CALDAY),
    WEEK        = ('W',         lambda d, n: d + relativedelta(weeks   = n),        dict(C = 7,     W = 1),                             TENOR_FREQUENCY.CALDAY),
    MONTH       = ('M',         lambda d, n: d + relativedelta(months  = n),        dict(M = 1,     Q = 1/3,    S = 1/6,    Y = 1/12),  TENOR_FREQUENCY.MONTH),
    QUARTER     = ('Q',         lambda d, n: d + relativedelta(months  = n * 3),    dict(M = 3,     Q = 1,      S = 0.5,    Y = 0.25),  TENOR_FREQUENCY.MONTH),
    HALF_YEAR   = ('S',         lambda d, n: d + relativedelta(months  = n * 6),    dict(M = 6,     Q = 2,      S = 1,      Y = 0.5),   TENOR_FREQUENCY.MONTH),
    YEAR        = ('Y',         lambda d, n: d + relativedelta(years   = n),        dict(M = 12,    Q = 4,      S = 2,      Y = 1),     TENOR_FREQUENCY.MONTH),
    SOM         = ('SOM',       lambda d, n: date(d.year, d.month, 1) + relativedelta(months=n),                            None,   None),
    EOM         = ('EOM',       lambda d, n: date(d.year, d.month, 1) + relativedelta(months=n+1) + relativedelta(days=-1), None,   None),

    #IMM_QUARTER = ( 'IMM',      lambda d, n: IMMQuarter.which( d ).ith( n ).last(), None,                                               None ),
)
# fmt: on


class PROPAGATE_DATES(NamedConstant):
    BACKWARD = ()  ## BACKWARD period propagation is more standard for G10 interest rate swaps
    FORWARD = ()


class RDate(Nucleus):
    """
    rd = RDate('1Y')
    dt = date(2025, 1, 1)
    rd.apply(dt, Calendar.existing_instance_by_id('FB'), BIZDAY_ROLL_RULE.FOLLOWING)
    -> date(2026, 1, 1)
    """

    # s_spot_tenors = { 'ON', 'TN', 'SN' }

    # -- RDate('3M') or RDate(TENOR_FREQUENCY.MONTH, 3)
    # def __init__(self, symbol_or_frequency = None, count: int = None):
    def __init__(self, symbol: str = None, freq: TENOR_FREQUENCY = None, count: int = None):
        if symbol is not None:
            match = re.match(r'(-?\d+)([a-zA-Z]+)', symbol)
            count = int(match.group(1))
            letter = match.group(2)

            freq = FREQUENCY_TABLE.primary_key(TENOR_PARAMS.CHAR, letter.upper())
            if freq is None:
                raise AttributeError(f"Invalid tenor symbol '{symbol}'")

        else:
            assert freq is not None, 'freq must be a valid TENOR_FREQUENCY'
            if count is None:
                count = 1

        self.freq = freq
        self.count = count

    def symbol(self) -> str:
        return f'{self.count}{FREQUENCY_TABLE[self.freq][TENOR_PARAMS.CHAR]}'

    # ---- Nucleus methods
    def to_str(self) -> str:
        return self.symbol()

    def serialize(self, embed: bool):
        return self.symbol()

    @classmethod
    def deserialize(cls, serialized_data) -> Nucleus:
        return cls(symbol=serialized_data)

    @classmethod
    def from_str(cls, s: str) -> Nucleus:
        return cls(symbol=s)

    @classmethod
    def from_any_xstr(cls, value) -> Nucleus:
        if isinstance(value, cls):
            return cls(freq=value.freq, count=value.count)

        if isinstance(value, tuple):
            assert len(value) == 2, 'tenor frequency and count are expected'
            return cls(freq=value[0], count=value[1])

        raise AssertionError('unexpected type')

    @classmethod
    def same_values(cls, value1, value2) -> bool:
        return value1.freq == value2.freq and value1.count == value2.count

    # ----

    def apply(self, d: date, cal: Calendar, roll_rule: BIZDAY_ROLL_RULE) -> date:
        if self.freq is TENOR_FREQUENCY.BIZDAY:
            not_rolled = cal.advance_bizdays(d, self.count)     ## roll to bizday for '0B'
        else:
            fn = FREQUENCY_TABLE[self.freq][TENOR_PARAMS.RELATIVE_DELTA]
            not_rolled = fn(d, self.count)

        return roll_rule(not_rolled, cal)

    @classmethod
    def apply_rule(cls, d: date, cal: Calendar, roll_rule: BIZDAY_ROLL_RULE, comma_separated_rdates_str: str) -> date:
        rdates = comma_separated_rdates_str.split(',')
        for rdate_symbol in rdates:
            rdate = RDate(symbol=rdate_symbol)
            d = rdate.apply(d, cal, roll_rule)
        return d

    def conversion_freq_multiplier(self, other_freq: TENOR_FREQUENCY) -> float:
        my_freq = self.freq
        if my_freq is other_freq:
            return 1.0

        dont_handle_freqs = (TENOR_FREQUENCY.BIZDAY, TENOR_FREQUENCY.CALDAY, TENOR_FREQUENCY.WEEK)
        if my_freq in dont_handle_freqs or other_freq in dont_handle_freqs:
            raise ValueError(f'cannot convert {my_freq} to {other_freq}')

        multiplier = FREQUENCY_TABLE[my_freq][TENOR_PARAMS.CONVERSIONS].get(FREQUENCY_TABLE[other_freq][TENOR_PARAMS.CHAR])
        if not multiplier:
            raise ValueError(f'cannot get a conversion multiple from {my_freq} to {other_freq}')

        return multiplier

    def equate_freq(self, other: RDate) -> tuple:
        if self.freq is other.freq:
            return (self, other)

        mult = self.conversion_freq_multiplier(other.freq)  # -- either int or 1/int
        mult_i = int(mult)
        if mult_i >= 1:
            return (RDate(freq=other.freq, count=self.count * mult_i), other)

        return (self, RDate(freq=self.freq, count=other.count * int(1 / mult)))

    def _fract_count_to_RDate(self, count: float, freq: TENOR_FREQUENCY, freq_to_try: TENOR_FREQUENCY) -> RDate:
        if math.isclose(count, round(count)):
            return RDate(freq=freq, count=round(count))

        conv_to_min_freq = self.conversion_freq_multiplier(freq_to_try)
        return RDate(freq=freq_to_try, count=round(conv_to_min_freq * count))

    def multadd(self, mult: float, add, freq_to_try_for_fract_count=None) -> RDate:
        if isinstance(add, (int, float)):
            if add:
                raise ValueError(f'cannot add a non-zero number {add} to RDate {self}: the result is ambiguous')

            return self._fract_count_to_RDate(mult * self.count, self.freq, freq_to_try_for_fract_count)

        if isinstance(add, str):
            try:
                add = RDate(add)
            except Exception as e:
                raise ValueError(f'cannot convert adder {add} to RDate') from e

        if isinstance(add, RDate):
            rd1, rd2 = self.equate_freq(add)
            return self._fract_count_to_RDate(mult * rd1.count + rd2.count, rd1.freq, freq_to_try_for_fract_count)

        raise ValueError(f'cannot calc a linear combination of {mult} * {self} + {add}')

    def __mul__(self, other: float) -> RDate:
        return self.multadd(other, 0, freq_to_try_for_fract_count=FREQUENCY_TABLE[self.freq][TENOR_PARAMS.MIN_FREQUENCY])

    def __rmul__(self, other: float) -> RDate:
        return self.multadd(other, 0, freq_to_try_for_fract_count=FREQUENCY_TABLE[self.freq][TENOR_PARAMS.MIN_FREQUENCY])

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            return self.multadd(1 / other, 0, freq_to_try_for_fract_count=FREQUENCY_TABLE[self.freq][TENOR_PARAMS.MIN_FREQUENCY])

        rd1, rd2 = self.equate_freq(other)
        return rd1.count / rd2.count

    def __add__(self, other) -> RDate:
        return self.multadd(1.0, other, freq_to_try_for_fract_count=FREQUENCY_TABLE[self.freq][TENOR_PARAMS.MIN_FREQUENCY])

    @classmethod
    def add_bizdays(cls, d: date, biz_days: int, cal: Calendar, roll_rule: BIZDAY_ROLL_RULE) -> date:
        not_rolled = cal.advance_bizdays(d, biz_days)
        return roll_rule(not_rolled, cal)

    @classmethod
    def roll_to_bizday(cls, d: date, cal: Calendar, roll_rule: BIZDAY_ROLL_RULE) -> date:
        return roll_rule(d, cal)

    class RELOP(NamedConstant):
        LT = date.__lt__
        GT = date.__gt__
        EQ = date.__eq__
        NE = date.__ne__
        LE = date.__le__
        GE = date.__ge__

    @classmethod
    def relop(cls, rel_op: RELOP, rd1: RDate, rd2: RDate, d: date, cal: Calendar, roll_rule: BIZDAY_ROLL_RULE) -> bool:
        d1 = rd1.apply(d, cal, roll_rule)
        d2 = rd2.apply(d, cal, roll_rule)
        return rel_op(d1, d2)

    @classmethod
    def from_tenors(cls, tenors_str: str, delim=',') -> list:
        tenors = tenors_str.split(delim)
        return [RDate(tenor.strip()) for tenor in tenors]

    def dates_schedule(
        self, start: date, end: date, calendar: Calendar, roll_rule: BIZDAY_ROLL_RULE, date_propagation: PROPAGATE_DATES, allow_stub=True
    ) -> list:
        rolled_start = roll_rule(start, calendar)
        assert rolled_start >= start, (
            f'rolled start date {rolled_start} is before non-working start date {start} according to calendar {calendar.name} and roll rule {roll_rule.name}'
        )
        rolled_end = roll_rule(end, calendar)
        assert rolled_end <= end, (
            f'rolled end date {rolled_end} is after non-working end date {end} according to calendar {calendar.name} and roll rule {roll_rule.name}'
        )

        if date_propagation == PROPAGATE_DATES.BACKWARD:
            begin = rolled_end
            finish = rolled_start
            dir = -1
            exceed = lambda x, y: x < y
            ex_or_eq = lambda x, y: x <= y
        else:
            begin = rolled_start
            finish = rolled_end
            dir = 1
            exceed = lambda x, y: x > y
            ex_or_eq = lambda x, y: x >= y

        step = self * dir

        prev_rolled_date = begin
        rolled_date = begin
        non_rolled_date = begin

        all_dates = []
        while ex_or_eq(finish, rolled_date):
            all_dates.append(rolled_date)
            non_rolled_date = step.apply(non_rolled_date, calendar, BIZDAY_ROLL_RULE.NO_ROLL)
            rolled_date = roll_rule(non_rolled_date, calendar)
            assert exceed(rolled_date, prev_rolled_date), (
                f'infinite loop: next date {rolled_date} vs previous date {prev_rolled_date} for date_propagation = {date_propagation.name}'
            )
            if exceed(rolled_date, finish):
                break
            prev_rolled_date = rolled_date

        if not allow_stub:
            assert prev_rolled_date == finish, f'the date sequence has a stub period bound by {prev_rolled_date} and {finish}'

        all_dates.sort()
        return all_dates

    def period_dates(
        self, start: date, end: date, calendar: Calendar, roll_rule: BIZDAY_ROLL_RULE, date_propagation: PROPAGATE_DATES, allow_stub=True
    ) -> tuple:
        all_dates = self.dates_schedule(start, end, calendar, roll_rule, date_propagation, allow_stub)
        start_dates = all_dates[:-1]
        end_dates = all_dates[1:]

        return start_dates, end_dates, all_dates

    ## if the tenor is not an integral multiple of the frequency (e.g., 30-month annual swap: tenor = 5S, freq = YEAR)
    ## then there would be a period "shorter than the frequency" (e.g., half-year in the 30-month annual swap)
    ## call such a period a STUB. it maybe in the front (1st period) for BACKWARD propagation or in the back (last period) for FORWARD
    def period_dates_for_tenor(
        self, start: date, tenor: RDate, calendar: Calendar, roll_rule: BIZDAY_ROLL_RULE, date_propagation: PROPAGATE_DATES, allow_stub=True
    ) -> tuple:
        start = roll_rule(start, calendar)
        end = tenor.apply(start, calendar, roll_rule)
        return self.period_dates(start, end, calendar, roll_rule, date_propagation, allow_stub)
