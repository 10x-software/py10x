from __future__ import annotations

import importlib
import math
from datetime import date

import pytest


@pytest.fixture(params=[False, True], ids=['py_curve', 'bcurve'])
def curve_backend(request):
    return request.param


@pytest.fixture
def curve_mod(curve_backend, monkeypatch):
    """Run curve tests against both Python and experimental C++ (BCurve) backends."""
    from xx_common.xxcommon_env_vars import XXCommonEnvVars

    monkeypatch.setenv('XXCOMMON_USE_CXX_CURVE', str(curve_backend))
    object.__getattribute__(XXCommonEnvVars, 'use_cxx_curve').fget.clear()

    import xx_common.curve as curve_mod

    importlib.reload(curve_mod)
    return curve_mod


def _seed_date_curve_dates(dc, d1: date, d2: date, *, cxx: bool) -> None:
    if cxx:
        dc.update(d1, 0.0, reset=False)
        dc.update(d2, 1.0, reset=True)
    else:
        dc.dates = [d1, d2]


def _assert_date_curve_dates(dc, d1: date, d2: date, *, cxx: bool) -> None:
    assert isinstance(dc.times[0], int)
    if cxx:
        assert list(dc.bcurve.dates) == [d1, d2]
    else:
        assert dc.dates == [d1, d2]


def _set_date_curve_beginning_of_time(dc, d: date, *, cxx: bool) -> None:
    if cxx:
        dc.bcurve.set_beginning_of_time(d)
    else:
        dc.beginning_of_time = dc._to_number(d)


def _configure_no_interp(c, params, ip_kind, *, cxx: bool) -> None:
    params.ip_kind = ip_kind.NO_INTERP
    if cxx:
        c.set_curve_params(ip_kind=ip_kind.NO_INTERP)
    else:
        c.params = params


@pytest.mark.usefixtures('curve_mod')
class TestCurve:
    @pytest.fixture(autouse=True)
    def _py_curve_only(self, curve_backend):
        if curve_backend:
            pytest.xfail('Numeric Curve tests are py-only for now')

    def test_update_inserts_sorted_and_overwrites(self, curve_mod):
        Curve = curve_mod.Curve
        c = Curve()

        # Insert out of order to check internal sorting
        c.update(5, 50.0, reset=False)
        c.update(1, 10.0, reset=False)
        c.update(3, 30.0, reset=False)

        # Overwrite existing point
        c.update(3, 35.0, reset=False)

        assert c.times == [1, 3, 5]
        assert c.values == [10.0, 35.0, 50.0]

    def test_value_linear_interpolation(self, curve_mod):
        Curve = curve_mod.Curve
        c = Curve()
        c.update_many([0.0, 1.0], [0.0, 2.0], reset=True)

        # Ensure interpolation is allowed for all t by setting a non-None beginning_of_time
        c.beginning_of_time = 0.0

        # Exact nodes
        assert c.value(0.0) == pytest.approx(0.0)
        assert c.value(1.0) == pytest.approx(2.0)

        # Linear interpolation between nodes
        assert c.value(0.5) == pytest.approx(1.0)

    def test_value_before_beginning_of_time_is_nan(self, curve_mod):
        Curve = curve_mod.Curve
        c = Curve()
        c.update_many([0.0, 10.0], [0.0, 100.0], reset=True)
        c.beginning_of_time = 5.0

        assert math.isnan(c.value(3.0))
        assert c.value(7.0) == pytest.approx(70.0)

    def test_value_returns_python_float(self, curve_mod):
        # scipy.interpolate.interp1d returns a 0-d numpy.ndarray; value() must
        # unwrap to a built-in float so callers don't get an array back.
        Curve = curve_mod.Curve
        c = Curve()
        c.update_many([0.0, 1.0], [0.0, 2.0], reset=True)
        c.beginning_of_time = 0.0

        # Interpolated point
        v_mid = c.value(0.5)
        assert type(v_mid) is float
        assert v_mid == pytest.approx(1.0)

        # Exact node
        v_node = c.value(1.0)
        assert type(v_node) is float
        assert v_node == pytest.approx(2.0)

        # Extrapolated point (default fill_value='extrapolate')
        v_extrap = c.value(2.0)
        assert type(v_extrap) is float
        assert v_extrap == pytest.approx(4.0)

    def test_no_interp_mode(self, curve_mod):
        Curve, CurveParams, IP_KIND = curve_mod.Curve, curve_mod.CurveParams, curve_mod.IP_KIND
        c = Curve()
        c.update_many([0.0, 1.0], [10.0, 20.0], reset=True)

        params = CurveParams()
        _configure_no_interp(c, params, IP_KIND, cxx=False)

        # Direct lookup for existing times
        assert c.value(0.0) == pytest.approx(10.0)
        assert c.value(1.0) == pytest.approx(20.0)

        # Missing time returns NaN
        v = c.value(0.5)
        assert math.isnan(v)

    def test_remove_and_perturb(self, curve_mod):
        Curve = curve_mod.Curve
        c = Curve()
        c.update_many([0, 1, 2], [10.0, 20.0, 30.0], reset=True)

        # Remove existing point
        assert c.remove(1) is True
        assert c.times == [0, 2]
        assert c.values == [10.0, 30.0]

        # Removing non-existing point
        assert c.remove(100) is False


class TestTwoFuncInterpolator:
    def test_requires_in_func_or_in_func_on_arrays(self):
        from xx_common.curve import TwoFuncInterpolator

        with pytest.raises(AssertionError):
            TwoFuncInterpolator(None, lambda t, v: v)

    def test_composed_interpolation(self):
        from xx_common.curve import TwoFuncInterpolator

        # in_func multiplies values by 2, out_func divides by 2 -- net effect is identity
        def in_func_on_arrays(xs, ys):
            return [2.0 * y for y in ys]

        def out_func(t, v):
            return v / 2.0

        tf = TwoFuncInterpolator(
            in_func=None,
            out_func=out_func,
            in_func_on_arrays=in_func_on_arrays,
        )

        xs = [0.0, 1.0]
        ys = [0.0, 10.0]

        ip = tf(xs, ys, kind='linear', fill_value='extrapolate', bounds_error=False)

        # At mid-point we should recover the simple linear interpolation of original ys
        assert ip(0.5) == pytest.approx(5.0)


@pytest.mark.usefixtures('curve_mod')
class TestDateCurve:
    def test_dates_set_and_get(self, curve_mod, curve_backend):
        DateCurve = curve_mod.DateCurve
        dc = DateCurve()

        d1 = date(2023, 1, 1)
        d2 = date(2023, 1, 5)
        _seed_date_curve_dates(dc, d1, d2, cxx=curve_backend)
        _assert_date_curve_dates(dc, d1, d2, cxx=curve_backend)

    def test_update_and_value(self, curve_mod, curve_backend):
        DateCurve = curve_mod.DateCurve
        dc = DateCurve()

        d1 = date(2023, 1, 1)
        d2 = date(2023, 1, 11)

        dc.update(d1, 0.0, reset=False)
        dc.update(d2, 10.0, reset=True)

        _set_date_curve_beginning_of_time(dc, d1, cxx=curve_backend)

        assert dc.value(d1) == pytest.approx(0.0)
        assert dc.value(d2) == pytest.approx(10.0)

        mid_date = d1 + (d2 - d1) / 2
        assert dc.value(mid_date) == pytest.approx(5.0)

    def test_no_interp_mode(self, curve_mod, curve_backend):
        DateCurve = curve_mod.DateCurve
        CurveParams, IP_KIND = curve_mod.CurveParams, curve_mod.IP_KIND
        dc = DateCurve()

        d1 = date(2023, 1, 1)
        d2 = date(2023, 1, 11)
        dc.update(d1, 10.0, reset=False)
        dc.update(d2, 20.0, reset=True)

        params = CurveParams()
        _configure_no_interp(dc, params, IP_KIND, cxx=curve_backend)

        assert dc.value(d1) == pytest.approx(10.0)
        assert dc.value(d2) == pytest.approx(20.0)

        mid_date = d1 + (d2 - d1) / 2
        assert math.isnan(dc.value(mid_date))

    def test_epoch_number_helpers(self, curve_mod, curve_backend):
        if curve_backend:
            pytest.xfail('cxx DateCurve has no _to_number/_from_number helpers')

        DateCurve = curve_mod.DateCurve
        dc = DateCurve()

        some_date = date(2020, 6, 15)
        num = dc._to_number(some_date)
        assert isinstance(num, int)
        assert dc._from_number(num) == some_date

    def test_beginning_of_time_as_date(self, curve_mod, curve_backend):
        DateCurve = curve_mod.DateCurve
        dc = DateCurve()

        some_date = date(2020, 6, 15)
        if curve_backend:
            dc.bcurve.set_beginning_of_time(some_date)
            assert dc.bcurve.beginning_of_time_as_date() == some_date
        else:
            rc = dc.set_values(beginning_of_time=some_date)
            assert rc
            assert isinstance(dc.beginning_of_time, int)
            assert dc.beginning_of_time_as_date() == some_date
