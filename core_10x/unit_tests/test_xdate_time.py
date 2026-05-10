import pytest
from datetime import date, datetime

from core_10x.xdate_time import XDateTime, MIN_CANONICAL_DATE


@pytest.fixture(autouse=True)
def _reset_xdatetime_format():
    """Restore XDateTime's global default format after each test.

    Other tests (e.g. test_environment_variables) may call
    XDateTime.set_default_format() and leave the process-global state
    changed.  This fixture isolates every test here from that side-effect.
    """
    original = XDateTime.s_default_format
    XDateTime.set_default_format(XDateTime.FORMAT_X10)
    yield
    XDateTime.set_default_format(original)


# ----------------------------------------------------------------------------
#   MIN_CANONICAL_DATE boundary
# ----------------------------------------------------------------------------

def test_min_canonical_date_value():
    assert MIN_CANONICAL_DATE == 10000101


# ----------------------------------------------------------------------------
#   int_to_date
# ----------------------------------------------------------------------------

def test_int_to_date_canonical_recent():
    assert XDateTime.int_to_date(20230115) == date(2023, 1, 15)


def test_int_to_date_canonical_year_2000():
    assert XDateTime.int_to_date(20000229) == date(2000, 2, 29)


def test_int_to_date_canonical_boundary():
    assert XDateTime.int_to_date(MIN_CANONICAL_DATE) == date(1000, 1, 1)


def test_int_to_date_ordinal():
    d = date(2023, 6, 15)
    assert XDateTime.int_to_date(d.toordinal()) == d


def test_int_to_date_ordinal_epoch():
    assert XDateTime.int_to_date(1) == date.fromordinal(1)


# ----------------------------------------------------------------------------
#   date_to_int
# ----------------------------------------------------------------------------

def test_date_to_int_ordinal_by_default():
    d = date(2023, 1, 15)
    assert XDateTime.date_to_int(d) == d.toordinal()


def test_date_to_int_ordinal_explicit():
    d = date(2023, 1, 15)
    assert XDateTime.date_to_int(d, ordinal=True) == d.toordinal()


def test_date_to_int_canonical():
    assert XDateTime.date_to_int(date(2023, 1, 15), ordinal=False) == 20230115


def test_date_to_int_canonical_edge_month_day():
    assert XDateTime.date_to_int(date(2000, 12, 31), ordinal=False) == 20001231


def test_date_to_int_roundtrip_canonical():
    d = date(1999, 3, 7)
    assert XDateTime.int_to_date(XDateTime.date_to_int(d, ordinal=False)) == d


def test_date_to_int_roundtrip_ordinal():
    d = date(2025, 7, 4)
    assert XDateTime.int_to_date(XDateTime.date_to_int(d, ordinal=True)) == d


# ----------------------------------------------------------------------------
#   str_to_date
# ----------------------------------------------------------------------------

def test_str_to_date_x10_format():
    assert XDateTime.str_to_date('20230115') == date(2023, 1, 15)


def test_str_to_date_iso_format():
    assert XDateTime.str_to_date('2023-01-15') == date(2023, 1, 15)


def test_str_to_date_us_format():
    assert XDateTime.str_to_date('01/15/2023') == date(2023, 1, 15)


def test_str_to_date_eu_format():
    assert XDateTime.str_to_date('15.01.2023') == date(2023, 1, 15)


def test_str_to_date_explicit_format():
    assert XDateTime.str_to_date('15-01-2023', '%d-%m-%Y') == date(2023, 1, 15)


def test_str_to_date_explicit_invalid_format_returns_none():
    assert XDateTime.str_to_date('not-a-date', '%Y%m%d') is None


def test_str_to_date_dateutil_fallback():
    result = XDateTime.str_to_date('Jan 15, 2023')
    assert result == date(2023, 1, 15)


def test_str_to_date_fully_unparseable_returns_none():
    assert XDateTime.str_to_date('gibberish-xyz-abc') is None


# ----------------------------------------------------------------------------
#   date_to_str
# ----------------------------------------------------------------------------

def test_date_to_str_default_format():
    assert XDateTime.date_to_str(date(2023, 1, 15)) == '20230115'


def test_date_to_str_iso_format():
    assert XDateTime.date_to_str(date(2023, 1, 15), '%Y-%m-%d') == '2023-01-15'


def test_date_to_str_us_format():
    assert XDateTime.date_to_str(date(2023, 1, 15), '%m/%d/%Y') == '01/15/2023'


# ----------------------------------------------------------------------------
#   set_default_format
# ----------------------------------------------------------------------------

def test_set_default_format_changes_date_to_str():
    XDateTime.set_default_format('%Y-%m-%d')
    assert XDateTime.date_to_str(date(2023, 1, 15)) == '2023-01-15'


def test_set_default_format_updates_formats_list():
    XDateTime.set_default_format('%d/%m/%Y')
    assert XDateTime.formats[0] == '%d/%m/%Y'
    assert XDateTime.s_default_format == '%d/%m/%Y'


# ----------------------------------------------------------------------------
#   datetime_to_str
# ----------------------------------------------------------------------------

def test_datetime_to_str_without_ms():
    dt = datetime(2023, 1, 15, 10, 30, 45)
    assert XDateTime.datetime_to_str(dt) == '20230115 10:30:45'


def test_datetime_to_str_with_ms():
    dt = datetime(2023, 1, 15, 10, 30, 45, 123456)
    assert XDateTime.datetime_to_str(dt, with_ms=True) == '20230115 10:30:45.123456'


def test_datetime_to_str_midnight():
    dt = datetime(2023, 6, 1, 0, 0, 0)
    assert XDateTime.datetime_to_str(dt) == '20230601 00:00:00'


# ----------------------------------------------------------------------------
#   str_to_datetime
# ----------------------------------------------------------------------------

def test_str_to_datetime_with_hms():
    dt = XDateTime.str_to_datetime('20230115 10:30:45')
    assert dt == datetime(2023, 1, 15, 10, 30, 45)


def test_str_to_datetime_with_hm_only():
    dt = XDateTime.str_to_datetime('20230115 10:30')
    assert dt is not None
    assert dt.hour == 10 and dt.minute == 30


def test_str_to_datetime_iso_via_dateutil():
    dt = XDateTime.str_to_datetime('2023-01-15T10:30:45')
    assert dt is not None
    assert dt.year == 2023 and dt.month == 1 and dt.day == 15


def test_str_to_datetime_unparseable_returns_none():
    assert XDateTime.str_to_datetime('not-a-datetime') is None


# ----------------------------------------------------------------------------
#   date_to_datetime
# ----------------------------------------------------------------------------

def test_date_to_datetime_produces_midnight():
    d = date(2023, 6, 15)
    dt = XDateTime.date_to_datetime(d)
    assert dt == datetime(2023, 6, 15, 0, 0, 0)


# ----------------------------------------------------------------------------
#   to_date  (converter dispatch)
# ----------------------------------------------------------------------------

def test_to_date_from_date():
    d = date(2023, 6, 1)
    assert XDateTime.to_date(d) is d


def test_to_date_from_datetime():
    dt = datetime(2023, 6, 1, 12, 0, 0)
    assert XDateTime.to_date(dt) == date(2023, 6, 1)


def test_to_date_from_canonical_int():
    assert XDateTime.to_date(20230601) == date(2023, 6, 1)


def test_to_date_from_iso_str():
    assert XDateTime.to_date('2023-06-01') == date(2023, 6, 1)


def test_to_date_unsupported_type_returns_none():
    assert XDateTime.to_date([2023, 6, 1]) is None
    assert XDateTime.to_date(None) is None


# ----------------------------------------------------------------------------
#   to_datetime  (converter dispatch)
# ----------------------------------------------------------------------------

def test_to_datetime_from_datetime():
    dt = datetime(2023, 6, 1, 10, 0, 0)
    assert XDateTime.to_datetime(dt) == dt


def test_to_datetime_from_date():
    d = date(2023, 6, 1)
    assert XDateTime.to_datetime(d) == datetime(2023, 6, 1, 0, 0, 0)


def test_to_datetime_from_ordinal_int():
    d = date(2023, 6, 1)
    assert XDateTime.to_datetime(d.toordinal()) == datetime(2023, 6, 1, 0, 0, 0)


def test_to_datetime_from_str():
    dt = XDateTime.to_datetime('20230601 10:30:00')
    assert dt is not None
    assert dt.year == 2023


def test_to_datetime_unsupported_type_returns_none():
    assert XDateTime.to_datetime([]) is None
    assert XDateTime.to_datetime(None) is None
