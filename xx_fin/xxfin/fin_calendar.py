from collections.abc import Callable
from datetime import date

import QuantLib as ql
from core_10x.global_cache import cache
from core_10x.named_constant import NamedConstant
from core_10x.trait_definition import T
from xxcommon.xxcalendar import Calendar


# note: keys are bloomberg codes
class KNOWN_CALENDARS(NamedConstant, data_type=Callable):
    # fmt: off
    US      = lambda: ql.UnitedStates(ql.UnitedStates.SOFR)
    FD      = lambda: ql.UnitedStates(ql.UnitedStates.FederalReserve)
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


