"""QuantLib bootstrap dates vs the native deposit and OIS conventions.

QuantLib is optional here: if the import fails, a stand-in records the helper
arguments and still lets the xxfin calendar fixture build.
"""

import sys
from datetime import date, timedelta
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest
from xxcommon.rdate import BIZDAY_ROLL_RULE, TENOR_FREQUENCY, RDate

_QL_MOCKED = False


class _QDate:
    def __init__(self, day, month, year):
        self._py = date(int(year), int(month), int(day))

    @staticmethod
    def from_date(d):
        if isinstance(d, _QDate):
            return _QDate(d._py.day, d._py.month, d._py.year)
        return _QDate(d.day, d.month, d.year)

    def to_date(self):
        return self._py

    def __le__(self, other):
        return self._py <= other._py

    def __iadd__(self, n):
        self._py += timedelta(days=int(n))
        return self


class _Settings:
    _instance = None

    def __init__(self):
        self.evaluationDate = _QDate(1, 1, 1900)

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


class _Calendar:
    def __init__(self, *args, **kwargs):
        self.args = args

    def isBusinessDay(self, d):
        return True

    def businessDaysBetween(self, *args, **kwargs):
        return 0


class _UnitedStates(_Calendar):
    SOFR = 0
    FederalReserve = 1


class _QLBase:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class _QLType(type):
    """Class factory so `ql.DateGeneration.Forward` and trait annotations both work."""

    def __getattr__(cls, item):
        child = _QLType(item, (_QLBase,), {})
        setattr(cls, item, child)
        return child


class _QLMock(ModuleType):
    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        obj = _QLType(name, (_QLBase,), {})
        setattr(self, name, obj)
        return obj


def _install_quantlib_mock():
    """Stand-in used only when `import QuantLib` fails.

    Tests patch the constructors they assert on. Calendar iteration still has to
    terminate so FinCalendar can materialize non-working days during the package fixture.
    """
    mod = _QLMock('QuantLib')
    mod.__file__ = '<quantlib-mock>'
    mod.__package__ = 'QuantLib'
    mod.Date = _QDate
    mod.Settings = _Settings
    mod.Calendar = _Calendar
    mod.UnitedStates = _UnitedStates
    for name in ('UnitedKingdom', 'TARGET', 'Switzerland', 'Japan', 'Australia', 'NewZealand', 'Canada'):
        setattr(mod, name, type(name, (_Calendar,), {}))
    sys.modules['QuantLib'] = mod
    return mod


try:
    import QuantLib as ql
except ImportError:
    ql = _install_quantlib_mock()
    _QL_MOCKED = True

from xxfin import ir_zero_rate_curve_ql as zql  # noqa: E402
from xxfin import ql_adapter  # noqa: E402
from xxfin.day_count_convention import DAY_COUNT_CONVENTION  # noqa: E402
from xxfin.ir_compounding import COMPOUNDING  # noqa: E402


class _StubCalendar:
    """Fixed business-day count so the bank calendar and the curve calendar can disagree."""

    def __init__(self, fixing_days):
        self.fixing_days = fixing_days
        self.seen_today = None

    def businessDaysBetween(self, today, start, *args, **kwargs):
        self.seen_today = today
        if today.to_date() == start.to_date():
            return 0
        return self.fixing_days


def _conventions(spot, bank_days=2, curve_days=1):
    bank = _StubCalendar(bank_days)
    curve = _StubCalendar(curve_days)
    mc = SimpleNamespace(
        mkt_name = 'SOFR',
        spot_offset = spot,
        settle_offset = RDate('2B'),
        ccy = SimpleNamespace(name = 'USD', bank_calendar = SimpleNamespace(ql_calendar = bank)),
        calendar = SimpleNamespace(ql_calendar = curve),
        settlement_calendar = SimpleNamespace(ql_calendar = curve),
        dc_convention = DAY_COUNT_CONVENTION.ACT360,
        fixed_leg_swap_dc_convention = DAY_COUNT_CONVENTION.ACT360,
        fixed_leg_swap_tenor_frequency = TENOR_FREQUENCY.YEAR,
        roll_rule = BIZDAY_ROLL_RULE.MOD_FOLLOWING,
        roll_rule_to_settle = BIZDAY_ROLL_RULE.FOLLOWING,
        compounding = COMPOUNDING.SIMPLE,
    )
    return mc, bank, curve


class _Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self


def test_overnight_index_settlement_days_are_zero():
    mc, _bank, _curve = _conventions(RDate('2B'))
    recorded = _Recorder()
    with patch.object(ql_adapter.ql, 'OvernightIndex', recorded):
        ql_adapter.QL.overnight_index(mc, forecast_curve = object())
    # settlement days are the second positional. Nonzero is a fixing lookback.
    assert recorded.calls[0][0][1] == 0


def test_deposit_fixing_days_follow_the_bank_calendar():
    md = date(2024, 3, 28)
    mc, bank, curve = _conventions(RDate('2B'))
    settings = ql.Settings.instance()
    saved = settings.evaluationDate
    settings.evaluationDate = ql.Date(1, 1, 1999)
    quotable = SimpleNamespace(quote = 0.05, tenor = RDate('3M'), start_date = date(2024, 4, 1))
    recorded = _Recorder()
    try:
        with patch.object(ql_adapter.ql, 'DepositRateHelper', recorded):
            ql_adapter.QL.deposit_helper(quotable, mc, md)
    finally:
        settings.evaluationDate = saved

    args = recorded.calls[0][0]
    assert args[2] == bank.fixing_days
    assert args[3] is bank
    assert bank.fixing_days != curve.fixing_days
    assert bank.seen_today.to_date() == md
    assert curve.seen_today is None


def test_overnight_deposit_keeps_the_curve_calendar():
    md = date(2024, 3, 28)
    mc, bank, curve = _conventions(RDate('2B'))
    quotable = SimpleNamespace(quote = 0.05, tenor = RDate('1B'), start_date = md)
    recorded = _Recorder()
    with patch.object(ql_adapter.ql, 'DepositRateHelper', recorded):
        ql_adapter.QL.deposit_helper(quotable, mc, md)
    args = recorded.calls[0][0]
    assert args[2] == 0
    assert args[3] is curve
    assert bank.seen_today is None


def test_sofr_fd_holiday_inside_the_spot_window():
    # Good Friday 2024-03-29 is an FD business day and a SOFR holiday, so Thursday's
    # T+2 spot is 2024-04-01 on FD (2 business days) and not on US (1 business day).
    if _QL_MOCKED:
        pytest.skip('native QuantLib calendars are not installed')
    bank = ql.UnitedStates(ql.UnitedStates.FederalReserve)
    curve = ql.UnitedStates(ql.UnitedStates.SOFR)
    probe = ql.Date(29, 3, 2024)
    md = date(2024, 3, 28)
    start = date(2024, 4, 1)
    bank_days = bank.businessDaysBetween(ql_adapter.QL.to_date(md), ql_adapter.QL.to_date(start))
    curve_days = curve.businessDaysBetween(ql_adapter.QL.to_date(md), ql_adapter.QL.to_date(start))
    assert bank.isBusinessDay(probe)
    assert not curve.isBusinessDay(probe)
    assert bank_days == 2
    assert curve_days == 1

    mc, _stub_bank, _stub_curve = _conventions(RDate('2B'))
    mc.ccy.bank_calendar.ql_calendar = bank
    mc.calendar.ql_calendar = curve
    quotable = SimpleNamespace(quote = 0.05, tenor = RDate('3M'), start_date = start)
    recorded = _Recorder()
    with patch.object(ql_adapter.ql, 'DepositRateHelper', recorded):
        ql_adapter.QL.deposit_helper(quotable, mc, md)
    args = recorded.calls[0][0]
    assert args[2] == bank_days
    assert args[3].isBusinessDay(probe)


def test_ois_helper_spot_lag_forward_and_not_end_of_month():
    mc, _bank, _curve = _conventions(RDate('2B'))
    quotable = SimpleNamespace(tenor = RDate('5Y'), quote = 0.03)
    recorded = _Recorder()
    with patch.object(ql_adapter.ql, 'OISRateHelper', recorded):
        ql_adapter.QL.swap_helper(quotable, mc, index = object())
    args, kwargs = recorded.calls[0]
    assert args[0] == mc.spot_offset.count
    assert kwargs['rule'] == ql.DateGeneration.Forward
    assert kwargs['endOfMonth'] is False


def test_ois_spot_lag_rejects_a_non_business_day_offset():
    mc, _bank, _curve = _conventions(RDate('2W'))
    quotable = SimpleNamespace(tenor = RDate('1Y'), quote = 0.01)
    with pytest.raises(ValueError, match = 'business days'):
        ql_adapter.QL.swap_helper(quotable, mc, index = object())


def test_evaluation_date_restored_when_bootstrap_raises():
    class _Res:
        dc_convention = DAY_COUNT_CONVENTION.ACT360
        compounding = COMPOUNDING.SIMPLE

    def _boom(*args, **kwargs):
        raise RuntimeError('bootstrap')

    settings = ql.Settings.instance()
    saved = settings.evaluationDate
    marker = ql.Date(2, 2, 2018)
    settings.evaluationDate = marker
    curve = SimpleNamespace(
        md_date = date(2024, 3, 28),
        mkt_conventions = SimpleNamespace(
            dc_convention = DAY_COUNT_CONVENTION.ACT360,
            compounding = COMPOUNDING.SIMPLE,
        ),
        quotables_by_class = {},
    )
    try:
        with (
            patch.object(zql, 'RateCurve', lambda **kwargs: _Res()),
            patch.object(zql.ql, 'PiecewiseLinearZero', _boom),
            pytest.raises(RuntimeError, match = 'bootstrap'),
        ):
            zql.ZeroRateCurveQL.payload_get(curve)
        assert settings.evaluationDate.to_date() == marker.to_date()
    finally:
        settings.evaluationDate = saved
