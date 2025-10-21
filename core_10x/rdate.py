from __future__ import annotations

import math
import re
from datetime import date

from dateutil.relativedelta import relativedelta

from core_10x.calendar import Calendar
from core_10x.named_constant import NamedConstant, NamedConstantTable
from core_10x.nucleus import Nucleus


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
    IMM_QUARTER = ()
    # fmt: on

class FREQUENCY_VALUES(NamedConstant):
    MKT_LITERAL     = ()
    RELDELTA_ARG    = ()
    CONVERSION      = ()
    MIN_CONV_FREQ   = ()

FREQUENCY_TABLE = NamedConstantTable(TENOR_FREQUENCY, FREQUENCY_VALUES)(
    #               MKT_LITERAL RELDELTA_ARG                                        CONVERSION                                          MIN_CONV_FREQ
    BIZDAY      = ('B',         None,                                               None,                                               None),
    CALDAY      = ('C',         lambda d, n: d + relativedelta(days    = n),        dict(C = 1,     W = 1/7),                           TENOR_FREQUENCY.CALDAY),
    WEEK        = ('W',         lambda d, n: d + relativedelta(weeks   = n),        dict(C = 7,     W = 1),                             TENOR_FREQUENCY.CALDAY),
    MONTH       = ('M',         lambda d, n: d + relativedelta(months  = n),        dict(M = 1,     Q = 1/3,    S = 1/6,    Y = 1/12),  TENOR_FREQUENCY.MONTH),
    QUARTER     = ('Q',         lambda d, n: d + relativedelta(months  = n * 3),    dict(M = 3,     Q = 1,      S = 0.5,    Y = 0.25),  TENOR_FREQUENCY.MONTH),
    HALF_YEAR   = ('S',         lambda d, n: d + relativedelta(months  = n * 6),    dict(M = 6,     Q = 2,      S = 1,      Y = 0.5),   TENOR_FREQUENCY.MONTH),
    YEAR        = ('Y',         lambda d, n: d + relativedelta(years   = n),        dict(M = 12,    Q = 4,      S = 2,      Y = 1),     TENOR_FREQUENCY.MONTH),

    #IMM_QUARTER = ( 'IMM',      lambda d, n: IMMQuarter.which( d ).ith( n ).last(), None,                                               None ),
)
# fmt: on


class RDate(Nucleus):
    """
    rd = RDate('1Y')
    dt = date(2025, 1, 1)
    rd.apply(dt, Calendar.existing_instance_by_id('FB'), BIZDAY_ROLL_RULE.FOLLOWING)
    -> date(2026, 1, 1)
    """

    # -- RDate('3M') or RDate(TENOR_FREQUENCY.MONTH, 3)
    def __init__(self, symbol_or_frequency=None, count: int = None):
        if isinstance(symbol_or_frequency, str):
            symbol = symbol_or_frequency
            match = re.match(r'(-?\d+)([a-zA-Z]+)', symbol)
            count = int(match.group(1))
            letters = match.group(2)

            self.tenor = FREQUENCY_TABLE.primaryKey(FREQUENCY_VALUES.MKT_LITERAL, letters.upper())
            if self.tenor is None:
                raise AttributeError(f"Invalid tenor type '{symbol}'")

            try:
                self.count = count
            except Exception as e:
                raise AttributeError(f"Invalid tenor '{symbol}'") from e

        elif isinstance(symbol_or_frequency, int):  # -- i.e., TENOR_FREQUENCY
            frequency = symbol_or_frequency
            if count is None:
                count = 1
            else:
                assert isinstance(count, int), f'count = {count} - must be an int'

            refs = FREQUENCY_TABLE[frequency]  # -- will throw if tenor is unknown
            self.tenor = frequency
            self.count = count
            symbol = refs.MKT_LITERAL
            assert symbol, f"Can't construct symbol from frequency = {frequency}"
            symbol = f'{count}{symbol}'

        elif isinstance(symbol_or_frequency, RDate):
            symbol = symbol_or_frequency.symbol
            self.tenor = symbol_or_frequency.tenor
            self.count = symbol_or_frequency.count

        else:
            raise ValueError('symbol_or_frequency must be either RDate, str or TENOR_FREQUENCY')

        self.symbol = symbol.upper()

    def __repr__(self):
        return self.symbol

    def _serialize(self, to_store: bool, embed_nx: bool, morphing_serializers: dict) -> str:
        return self.symbol

    @classmethod
    def _deserialize(cls, data, morphing_deserializers: dict) -> Nucleus:
        return cls(data)

    def symbol(self) -> str:
        return self.symbol

    def apply(self, d: date, cal: Calendar, roll_rule: BIZDAY_ROLL_RULE) -> date:
        if self.tenor == TENOR_FREQUENCY.BIZDAY:
            not_rolled = cal.advance_bizdays(d, self.count)
        else:
            fn = FREQUENCY_TABLE[self.tenor][FREQUENCY_VALUES.RELDELTA_ARG]
            not_rolled = fn(d, self.count)

        return roll_rule(not_rolled, cal)

    def conversion_freq_multiplier(self, other_freq: TENOR_FREQUENCY) -> float:
        my_freq = self.tenor
        if my_freq == other_freq:
            return 1.0

        dont_handle_freqs = (TENOR_FREQUENCY.BIZDAY, TENOR_FREQUENCY.CALDAY, TENOR_FREQUENCY.WEEK)
        if my_freq in dont_handle_freqs or other_freq in dont_handle_freqs:
            raise ValueError(f'cannot convert {TENOR_FREQUENCY.labelFromValue(my_freq)} to {TENOR_FREQUENCY.labelFromValue(other_freq)}')

        multiple = FREQUENCY_TABLE[my_freq].CONVERSION.get(FREQUENCY_TABLE[other_freq].MKT_LITERAL)
        if not multiple:
            raise ValueError(
                f'cannot get a conversion multiple from {TENOR_FREQUENCY.labelFromValue(my_freq)} to {TENOR_FREQUENCY.labelFromValue(other_freq)}'
            )

        return multiple

    def equate_freq(self, other) -> tuple:
        if isinstance(other, str):
            try:
                other = RDate(other)
            except Exception as e:
                raise ValueError(f'{other} - failed to convert to RDate') from e

        if not isinstance(other, RDate):
            raise ValueError('other must be either RDate or convertible str')

        if self.tenor == other.tenor:
            return (self, other)

        mult = self.conversion_freq_multiplier(other.tenor)  # -- either int or 1/int
        if int(mult) >= 1:
            return (RDate(symbol_or_frequency=other.tenor, count=self.count * int(mult)), other)

        return (self, RDate(symbol_or_frequency=self.tenor, count=other.count * int(1 / mult)))

    def _fract_count_to_RDate(self, count: float, freq: TENOR_FREQUENCY, freq_to_try: TENOR_FREQUENCY) -> RDate:
        if math.isclose(count, round(count)):
            return RDate(symbol_or_frequency=freq, count=round(count))

        if freq_to_try is not None:
            conv_to_min_freq = self.conversion_freq_multiplier(freq_to_try)
            return RDate(symbol_or_frequency=freq_to_try, count=round(conv_to_min_freq * count))

        raise ValueError(f'cannot crate RDate: count = {count} is not integral')

    def multadd(self, mult: float, add, freq_to_try_for_fract_count=None) -> RDate:
        if isinstance(add, (int, float)):
            if add:
                raise ValueError(f'cannot add a non-zero number {add} to RDate {self}: the result is ambiguous')

            return self._fract_count_to_RDate(mult * self.count, self.tenor, freq_to_try_for_fract_count)

        if isinstance(add, str):
            try:
                add = RDate(add)
            except Exception as e:
                raise ValueError(f'cannot convert adder {add} to RDate') from e

        if isinstance(add, RDate):
            rd1, rd2 = self.equate_freq(add)
            return self._fract_count_to_RDate(mult * rd1.count + rd2.count, rd1.tenor, freq_to_try_for_fract_count)

        raise ValueError(f'cannot calc a linear combination of {mult} * {self} + {add}')

    def __mul__(self, other: float) -> RDate:
        return self.multadd(other, 0, freq_to_try_for_fract_count=FREQUENCY_TABLE[self.tenor].MIN_CONV_FREQ)

    def __rmul__(self, other: float) -> RDate:
        return self.multadd(other, 0, freq_to_try_for_fract_count=FREQUENCY_TABLE[self.tenor].MIN_CONV_FREQ)

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            return self.multadd(1 / other, 0, freq_to_try_for_fract_count=FREQUENCY_TABLE[self.tenor].MIN_CONV_FREQ)

        rd1, rd2 = self.equate_freq(other)
        return rd1.count / rd2.count

    def __add__(self, other) -> RDate:
        return self.multadd(1.0, other, freq_to_try_for_fract_count=FREQUENCY_TABLE[self.tenor].MIN_CONV_FREQ)

    @classmethod
    def addBizDays(cls, d: date, biz_days: int, cal: Calendar, roll_rule: BIZDAY_ROLL_RULE) -> date:
        not_rolled = cal.addBizDays(d, biz_days)
        return roll_rule(not_rolled, cal)

    @classmethod
    def rollToBizDay(cls, d: date, cal: Calendar, roll_rule: BIZDAY_ROLL_RULE) -> date:
        return roll_rule(d, cal)

    class RELOP(NamedConstant):
        LT = date.__lt__
        GT = date.__gt__
        EQ = date.__eq__
        NE = date.__ne__
        LE = date.__le__
        GE = date.__ge__

    @classmethod
    def relOp(cls, rel_op: RELOP, rd1: RDate, rd2: RDate, d: date, cal: Calendar, roll_rule: BIZDAY_ROLL_RULE) -> bool:
        d1 = rd1.apply(d, cal, roll_rule)
        d2 = rd2.apply(d, cal, roll_rule)
        return rel_op(d1, d2)
