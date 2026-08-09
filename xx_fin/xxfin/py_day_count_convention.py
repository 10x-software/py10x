import calendar
from datetime import date

from core_10x.named_constant import NamedConstant


def act360(d1: date, d2: date) -> float:
    return (d2 - d1).days / 360.0

def act365(d1: date, d2: date) -> float:
    return (d2 - d1).days / 365.0

def actact(d1: date, d2: date) -> float:
    from_year = d1.year
    from_year_num_days = (date(from_year + 1, 1, 1) - date(from_year, 1, 1)).days
    to_year = d2.year
    if from_year == to_year:
        return (d2 - d1).days / from_year_num_days

    to_year_num_days = (date(to_year + 1, 1, 1) - date(to_year, 1, 1)).days
    # days remaining in start/end year via next Jan 1 (Dec 31 deltas undercount by 1)
    frac1 = (date(from_year + 1, 1, 1) - d1).days / from_year_num_days
    frac2 = (date(to_year + 1, 1, 1) - d2).days / to_year_num_days
    return (frac1 - frac2) + (to_year - from_year)

def bb30360(d1: date, d2: date) -> float:
    from_day = d1.day
    to_day = d2.day

    if from_day == 31:
        from_day = 30
    if to_day == 31 and from_day in (30, 31):
        to_day = 30

    return (d2.year - d1.year) + (d2.month - d1.month) / 12 + (to_day - from_day) / 360

def us30360(d1: date, d2: date) -> float:
    from_day = d1.day
    to_day = d2.day


    from_month_last_day = d1.replace(day = calendar.monthrange(d1.year, d1.month)[1])
    if from_month_last_day == d1:
        from_day = 30

    if to_day == 31 and from_day in (30, 31):
        to_day = 30

    return (d2.year - d1.year) + (d2.month - d1.month) / 12 + (to_day - from_day) / 360

def eb30360(d1: date, d2: date) -> float:
    """
    Eurobond basis, a.k.a. 30E/360 in Bloomberg (cbonds.com/glossary/30e-360)
    Most of European IBORs are probably 'eb30360'
    """
    from_day = d1.day
    to_day = d2.day

    if from_day == 31:
        from_day = 30

    if to_day == 31:
        to_day = 30

    return (d2.year - d1.year) + (d2.month - d1.month) / 12 + (to_day - from_day) / 360

#---- TODO: according to ISDA (check!): Act/365 is ActAct, ACT/365Fixed (ACT/365F, ACT/365.Fixed) is Act365

class DAY_COUNT_CONVENTION(NamedConstant):
    """
    Usage: DAY_COUNT_CONVENTION.ACT365(date_from, date_to) -> float
    """
    ACT360  = act360
    ACT365  = act365
    ACTACT  = actact
    BB30360 = bb30360
    US30360 = us30360
    EB30360 = eb30360

def dc_fractions_for_dates( dates: list, convention: DAY_COUNT_CONVENTION ) -> list:
    return [ convention( dates[i], dates[i+1]) for i in range(len(dates)-1) ]