from core_10x.named_constant import NamedConstant
from cxxfin import BDayCountConvention


class DAY_COUNT_CONVENTION(NamedConstant, BDayCountConvention, symbols_from = BDayCountConvention):
    """
    Usage: DAY_COUNT_CONVENTION.ACT365(date_from, date_to) -> float
    """

def dc_fractions_for_dates( dates: list, convention: DAY_COUNT_CONVENTION ) -> list:
    return [ convention( dates[i], dates[i+1]) for i in range(len(dates)-1) ]