from __future__ import annotations

import bisect
import math
from datetime import date, timedelta
from typing import Any

from scipy import interpolate

from core_10x.named_constant import NamedConstant
from core_10x.traitable import RC, RC_TRUE, RT, AnonymousTraitable, M, T, Traitable


class IP_KIND(NamedConstant, lowercase_values=True):
    #-- NOTE: enum labels specify the minimum number of points required!
    LINEAR      = ( 2, )
    NEAREST     = ( 2, )
    NEAREST_UP  = ( 2, )
    PREVIOUS    = ( 2, )    #-- return the previous value of the point
    NEXT        = ( 2, )    #-- ------ the next ----
    ZERO        = ( 1, )    #-- spline interp of zeroth order
    SLINEAR     = ( 2, )    #-- spline interp of first order
    QUADRATIC   = ( 3, )    #-- spline interp of second order
    CUBIC       = ( 4, )    #-- spline interp of third order

    NO_INTERP   = ( 0, )    #-- NO interp outside of given nodes

class CurveParams(Traitable):
    DEFAULT_INTERPOLATOR = interpolate.interp1d

    interpolator: Any   = RT(default = DEFAULT_INTERPOLATOR)
    ip_kind: IP_KIND    = RT(IP_KIND.LINEAR)
    assume_sorted: bool = RT(True)
    copy: bool          = RT(False)
    fill_value: Any     = RT('extrapolate')     ## it's this str or a tuple (curve.values[0], curve.values[-1]) for flat extrapolation
    bounds_error: bool  = RT(False)

class Curve(AnonymousTraitable):
    times: list         = T([])       #-- only ints or floats are allowed
    values: list        = T([])
    params: CurveParams = RT()

    beginning_of_time: Any  = T(None)    #-- may be float or int

    interpolator: Any       = RT()
    min_curve_size: int     = RT()

    def params_get(self) -> CurveParams:
        return CurveParams()

    def min_curve_size_get(self) -> int:
        return self.params.ip_kind.label

    def start_time(self):
        times = self.times
        return times[0] if times else None

    def end_time(self):
        times = self.times
        return times[-1] if times else None

    def update(self, t, value, reset=True):
        if type(value) is not float:  # -- TODO: we sometimes have np.floats
            value = float(value)

        times = self.times
        values = self.values
        i = bisect.bisect_left(times, t)
        if i >= len(times):
            times.append(t)
            values.append(value)
        else:
            if times[i] == t:
                values[i] = value
            else:
                times.insert(i, t)
                values.insert(i, value)

        self.times = times
        self.values = values
        if reset:
            self.reset()

    def update_many(self, times, values, reset=True):
        assert len(times) == len(values), 'times and values size mismatch'
        for i, t in enumerate(times):
            self.update(t, values[i], reset=False)

        if reset:
            self.reset()

    def remove(self, t, reset=True) -> bool:
        times = self.times
        if t not in times:
            return False

        values = self.values
        i = times.index(t)
        times.pop(i)
        values.pop(i)
        if reset:
            self.reset()

        return True

    ## default; maybe no need other than reinforce default (could be done by invalidation?)
    ## extrapolate according to the interpolation method
    def extrapolate_params(self) -> CurveParams:
        params = self.params
        params.bounds_error = False
        params.fill_value   = 'extrapolate'
        self.params = params    ## TODO: is this right?
        self.reset()
        return params

    ## extrapolate flat left (by the first value) and right (by last value)
    def flat_extrapolate_params(self) -> CurveParams:
        params = self.params
        params.bounds_error = False
        params.fill_value   = (self.values[0], self.values[-1])     ## initial type declaration in the CurveParams class was str for the default 'extrapolate'; this is a tuple, which is also acceptable by the scipy.interpolate.interp1d()
        self.params = params    ## TODO: is this right?
        self.reset()
        return params

    def interpolator_get(self):
        params = self.params
        return params.interpolator(
            self.times, self.values,
            kind            = params.ip_kind.value,
            assume_sorted   = params.assume_sorted,
            copy            = params.copy,
            fill_value      = params.fill_value,
            bounds_error    = params.bounds_error,
        )

    def value(self, t) -> float:
        times = self.times

        if self.params.ip_kind is IP_KIND.NO_INTERP:
            return self.values[times.index(t)] if t in times else math.nan

        if len(times) < self.min_curve_size:
            if t in times:
                return self.values[times.index(t)]

        bot = self.beginning_of_time
        return float(self.interpolator(t)) if (bot is not None) or (t >= bot) else math.nan

    def values_at(self, dates) -> tuple:
        return tuple(self.value(d) for d in dates)

    def reset(self):
        self.invalidate_value('interpolator')


class TwoFuncInterpolator:
    def __init__(self, in_func, out_func, in_func_on_arrays=None, _interpolator=interpolate.interp1d):
        if in_func:
            in_func_on_arrays = lambda list_x, list_y: [in_func(x, list_y[i]) for i, x in enumerate(list_x)]

        assert in_func_on_arrays, 'either in_func or in_func_on_arrays must be provided'

        self.in_func = in_func_on_arrays
        self.out_func = out_func
        self.interpolator = _interpolator

    def __call__(self, x, y, **kwargs):
        values = self.in_func(x, y)
        ip_method = self.interpolator(x, values, **kwargs)
        out_func = self.out_func

        def _method(t):
            v = ip_method(t)
            return out_func(t, v)

        return _method


class DateCurve(Curve):
    beginning_of_time: int  = M()
    dates: list             = RT()

    s_epoch_date = date(1970, 1, 1)

    @classmethod
    def _to_number(cls, d) -> int:
        if isinstance(d, date):
            return (d - cls.s_epoch_date).days
        elif isinstance(d, int):
            return d

        raise ValueError(f'Unexpected value {d}')

    @classmethod
    def _from_number(cls, x: int) -> date:
        return cls.s_epoch_date + timedelta(days=x)

    def dates_get(self) -> list:
        f = self._from_number
        return [f(x) for x in self.times]

    def dates_set(self, trait, value) -> RC:
        f = self._to_number     #-- TODO: possibly improve performance by using a different f (which doesn't check the type)
        times = [f(d) for d in value]
        return self.set_value('times', times)

    def beginning_of_time_set(self, trait, d) -> RC:
        t = self._to_number(d)
        self.raw_set_value(trait, t)
        return RC_TRUE

    def beginning_of_time_as_date(self) -> date:
        return self._from_number(self.beginning_of_time)

    def start_time(self) -> date:
        times = self.dates
        return times[0] if times else None

    def end_time(self) -> date:
        times = self.dates
        return times[-1] if times else None

    def update(self, d: date, value, reset=True):
        x = self._to_number(d)
        super().update(x, value, reset=reset)

    def reset(self):
        super().reset()
        self.invalidate_value('dates')

    def value(self, d: date) -> float:
        x = self._to_number(d)
        return super().value(x)

    def remove(self, d, reset=True):
        t = self._to_number(d)
        if super().remove(t, reset=reset):
            self.invalidate_value('dates')

    def dates_values(self, min_date: date = None, max_date: date = None) -> list:
        dates = self.dates
        values = self.values
        return [(d, v) for d, v in zip(dates, values, strict=True) if (not min_date or d >= min_date) and (not max_date or d <= max_date)]
