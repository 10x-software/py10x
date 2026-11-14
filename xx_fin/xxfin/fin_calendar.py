from collections.abc import Callable
from datetime import date, timedelta

import QuantLib as ql
from core_10x.global_cache import cache
from core_10x.named_constant import NamedConstant
from core_10x.trait_definition import T
from xxcommon.xxcalendar import Calendar


def good_friday(year: int) -> date:
    #-- Anonymous Gregorian (Meeus/Jones/Butcher) Easter algorithm; QuantLib's Python API exposes none
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month, day = divmod(h + l_ - 7 * m + 114, 31)
    return date(year, month, day + 1) - timedelta(days=2)


def ice_futures_europe_oil() -> ql.Calendar:
    """ICE Futures Europe oil (Brent, WTI): closed only on 1 Jan, Good Friday and 25 Dec, with no in-lieu days.

    Per the IFEU Trading Schedule; UK bank holidays and US holidays are trading days (some with early close).
    """
    cal = ql.BespokeCalendar('ICE Futures Europe oil')  # -- a new BespokeCalendar does not share holidays with others
    cal.addWeekend(ql.Saturday)
    cal.addWeekend(ql.Sunday)
    for year in range(ql.Date.minDate().year(), ql.Date.maxDate().year() + 1):
        for d in (date(year, 1, 1), good_friday(year), date(year, 12, 25)):
            cal.addHoliday(ql.Date.from_date(d))
    return cal


# note: keys are bloomberg codes
class KNOWN_CALENDARS(NamedConstant, data_type=Callable):
    # fmt: off
    US      = lambda: ql.UnitedStates(ql.UnitedStates.SOFR)
    FD      = lambda: ql.UnitedStates(ql.UnitedStates.FederalReserve)
    NYM     = lambda: ql.UnitedStates(ql.UnitedStates.NYSE)     ## NYMEX energy: no-settlement days match NYSE's; not US (SOFR), which closes on Columbus/Veterans Day
    ICE     = ice_futures_europe_oil                            ## ICE Futures Europe oil; not GB: trades on UK bank holidays
    GB      = ql.UnitedKingdom
    EUTA    = ql.TARGET
    SZ      = ql.Switzerland    ## changed from SW to bbg code
    JP      = ql.Japan
    AU      = ql.Australia
    NZ      = ql.NewZealand
    CA      = ql.Canada
    # fmt: on

class FinCalendar(Calendar):
    ql_calendar_name: KNOWN_CALENDARS = T()

    ql_calendar: ql.Calendar
    start_date: date = date(1970, 1, 1)
    end_date: date = date(2070, 1, 1)

    @classmethod
    @cache
    def none(cls):
        return FinCalendar(_replace = True, name = '__none__', non_working_days = [])


    def ql_calendar_name_get(self):
        return KNOWN_CALENDARS.from_str(self.name)

    def ql_calendar_get(self):
        return self.ql_calendar_name.value()

    def non_working_days_get(self):
        try:
            cal = self.ql_calendar
        except Exception:
            return super().non_working_days_get()

        def _gen():
            d = ql.Date.from_date(self.start_date)
            ed = ql.Date.from_date(self.end_date)
            while d <= ed:
                if not cal.isBusinessDay(d):
                    yield d.to_date()
                d += 1

        return list(_gen())


