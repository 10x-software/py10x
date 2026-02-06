from __future__ import annotations

import math
from datetime import date

import pytest
from core_10x.curve import IP_KIND, Curve, CurveParams, DateCurve, TwoFuncInterpolator


class TestCurve:
    def test_update_inserts_sorted_and_overwrites(self):
        c = Curve()

        # Insert out of order to check internal sorting
        c.update(5, 50.0, reset=False)
        c.update(1, 10.0, reset=False)
        c.update(3, 30.0, reset=False)

        # Overwrite existing point
        c.update(3, 35.0, reset=False)

        assert c.times == [1, 3, 5]
        assert c.values == [10.0, 35.0, 50.0]

    def test_value_linear_interpolation(self):
        c = Curve()
        c.update_many([0.0, 1.0], [0.0, 2.0], reset=True)

        # Ensure interpolation is allowed for all t by setting a non-None beginning_of_time
        c.beginning_of_time = 0.0

        # Exact nodes
        assert c.value(0.0) == pytest.approx(0.0)
        assert c.value(1.0) == pytest.approx(2.0)

        # Linear interpolation between nodes
        assert c.value(0.5) == pytest.approx(1.0)

    def test_no_interp_mode(self):
        c = Curve()
        c.update_many([0.0, 1.0], [10.0, 20.0], reset=True)

        params = CurveParams()
        params.ip_kind = IP_KIND.NO_INTERP
        c.params = params

        # Direct lookup for existing times
        assert c.value(0.0) == pytest.approx(10.0)
        assert c.value(1.0) == pytest.approx(20.0)

        # Missing time returns NaN
        v = c.value(0.5)
        assert math.isnan(v)

    def test_remove_and_perturb(self):
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
        with pytest.raises(AssertionError):
            TwoFuncInterpolator(None, lambda t, v: v)

    def test_composed_interpolation(self):
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


class TestDateCurve:
    def test_dates_set_and_get(self):
        dc = DateCurve()

        d1 = date(2023, 1, 1)
        d2 = date(2023, 1, 5)
        dc.dates = [d1, d2]

        # Internal representation must be integer days from epoch
        assert isinstance(dc.times[0], int)
        assert dc.dates == [d1, d2]

    def test_update_and_value(self):
        dc = DateCurve()

        d1 = date(2023, 1, 1)
        d2 = date(2023, 1, 11)

        dc.update(d1, 0.0, reset=False)
        dc.update(d2, 10.0, reset=True)

        # Allow interpolation across the whole range
        dc.beginning_of_time = dc._to_number(d1)

        assert dc.value(d1) == pytest.approx(0.0)
        assert dc.value(d2) == pytest.approx(10.0)

        mid_date = d1 + (d2 - d1) / 2
        assert dc.value(mid_date) == pytest.approx(5.0)

    def test_beginning_of_time_helpers(self):
        dc = DateCurve()

        some_date = date(2020, 6, 15)
        num = dc._to_number(some_date)
        assert isinstance(num, int)
        assert dc._from_number(num) == some_date

        # beginning_of_time_set stores numeric value but exposes date via helper
        rc = dc.beginning_of_time_set('beginning_of_time', some_date)
        assert rc
        assert isinstance(dc.beginning_of_time, int)
        assert dc.beginning_of_time_as_date() == some_date
