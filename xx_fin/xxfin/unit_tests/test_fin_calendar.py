from datetime import date

import pytest
import QuantLib as ql
from core_10x.exec_control import CACHE_ONLY, DEBUG_ON
from infra_10x.duckdb_store import DuckDbStore
from py10x_kernel import BTraitableProcessor
from xxfin.fin_calendar import KNOWN_CALENDARS, FinCalendar, good_friday


def _holidays(cal: ql.Calendar, year: int) -> list[date]:
    return [d.to_date() for d in ql.Calendar.holidayList(cal, ql.Date(1, 1, year), ql.Date(31, 12, year))]


def test_good_friday_matches_quantlib_uk():
    uk = ql.UnitedKingdom()
    for year in range(1970, 2071):
        gf = ql.Date.from_date(good_friday(year))
        assert gf.weekday() == ql.Friday
        assert uk.isHoliday(gf) and uk.isHoliday(gf + 3), year  # -- Good Friday and Easter Monday


def test_ice_oil_calendar():
    """Dates from the IFEU Trading Schedule (Oil), November 2026 edition."""
    ice = KNOWN_CALENDARS.ICE.value()
    assert _holidays(ice, 2026) == [date(2026, 1, 1), date(2026, 4, 3), date(2026, 12, 25)]
    assert _holidays(ice, 2027) == [date(2027, 1, 1), date(2027, 3, 26)]  # -- 25 Dec 2027 is a Saturday: no in-lieu day

    uk_bank_holidays = [date(2026, 4, 6), date(2026, 5, 4), date(2026, 5, 25), date(2026, 8, 31), date(2026, 12, 28)]
    us_holidays = [date(2026, 1, 19), date(2026, 7, 3), date(2026, 11, 26), date(2027, 12, 24), date(2027, 12, 31)]
    for d in uk_bank_holidays + us_holidays + [date(2027, 12, 27), date(2027, 12, 28), date(2028, 1, 3)]:
        assert ice.isBusinessDay(ql.Date.from_date(d)), d


def test_nym_calendar():
    nym = KNOWN_CALENDARS.NYM.value()
    us = KNOWN_CALENDARS.US.value()
    assert _holidays(nym, 2026) == [
        date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3), date(2026, 5, 25),
        date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25),
    ]  # fmt: skip
    for d in (date(2026, 10, 12), date(2026, 11, 11)):  # -- Columbus Day, Veterans Day
        assert nym.isBusinessDay(ql.Date.from_date(d)) and not us.isBusinessDay(ql.Date.from_date(d)), d


def test_fin_calendar_by_name():
    with CACHE_ONLY():
        ice = FinCalendar(name='ICE')
        assert date(2026, 4, 3) in ice.non_working_days
        assert date(2026, 5, 4) not in ice.non_working_days


def test_save():
    with BTraitableProcessor.create_root(), DuckDbStore():
        assert not FinCalendar.existing_instance(name='US', _throw=False)
        with pytest.raises(ValueError, match=r'.*Instance does not exist.*'):
            FinCalendar.from_str('US|')
        with BTraitableProcessor.create_root():
            cal = FinCalendar(name='US')
            assert cal._rev == 0
            cal.save().throw()
            assert cal._rev == 1

        # cal = FinCalendar(name='US')
        cal = FinCalendar.existing_instance(name='US')
        assert cal.non_working_days
        assert cal.is_set(cal.T.non_working_days.trait)

        assert cal == FinCalendar.from_str('US|')
