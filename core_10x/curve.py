import bisect
import math
from datetime import date, timedelta
from typing import Any

from scipy import interpolate

from core_10x.named_constant import NamedConstant
from core_10x.traitable import RC, RC_TRUE, RT, T, Traitable


class IP_KIND(NamedConstant, lowercase_values=True):  # noqa: N801
    # fmt: off
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
    # fmt: on

    # @classmethod
    # def labelFromValue( cls, value ) -> int:
    #     return int( super().labelFromValue( value ) )
    #
    # @classmethod
    # def defaultValueForName( cls, name: str ) -> str:
    #     return name.replace( '_', '-' ).lower()


class CurveParams(Traitable):
    # fmt: off
    DEFAULT_INTERPOLATOR = interpolate.interp1d

    interpolator: Any   = RT(default = DEFAULT_INTERPOLATOR)
    ip_kind: IP_KIND    = T(IP_KIND.LINEAR)
    assume_sorted: bool = T(True)
    copy: bool          = T(False)
    fill_value: str     = T('extrapolate')
    bounds_error: bool  = T(False)
    # fmt: on


class Curve(Traitable):
    # fmt: off
    times: list         = T([])       #-- only ints or floats are allowed
    values: list        = T([])
    params: CurveParams = T(T.EMBEDDED)

    beginning_of_time: Any  = T(None)    #-- may be float or int

    interpolator: Any       = RT()
    min_curve_size: int     = RT()
    # fmt: on

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

    def perturb(self, t, new_value, perturb_existing_only=False):
        if perturb_existing_only:
            assert t in self.times, f't = {t} is not in the curve'

        values = self.values
        self.invalidate_value('values')
        self.values = values
        self.update(t, new_value)

    def perturb_shift(self, t, value_shift, perturb_existing_only=False):
        self.perturb(t, self.value(t) + value_shift, perturb_existing_only)

    def perturb_proportional(self, t, value_shift_mult, perturb_existing_only=False):
        self.perturb(t, self.value(t) * value_shift_mult, perturb_existing_only)

    def interpolator_get(self):
        params = self.params
        # fmt: off
        return params.interpolator(
            self.times, self.values,
            kind            = params.ip_kind,
            assume_sorted   = params.assume_sorted,
            copy            = params.copy,
            fill_value      = params.fill_value,
            bounds_error    = params.bounds_error,
        )
        # fmt: on

    def value(self, t) -> float:
        times = self.times

        if self.params.ip_kind is IP_KIND.NO_INTERP:
            return self.values[times.index(t)] if t in times else math.nan

        if len(times) < self.min_curve_size:
            if t in times:
                return self.values[times.index(t)]

        bot = self.beginning_of_time
        return float(self.interpolator(t)) if (not bot) or (t >= bot) else math.nan

    def values_at(self, dates) -> tuple:
        return tuple(self.value(d) for d in dates)

    def reset(self):
        self.invalidate_value('interpolator')

    @classmethod
    def _uniqueTimesValues(cls, times: list, values: list, keep_last_update: bool) -> tuple:  # noqa: N802
        assert len(times) == len(values), f'{len(times)} != {len(values)}: sizes of times and values must be equal'

        last_t = times[0]
        last_i = 0
        times_unique = [last_t]
        values_unique = [values[0]]

        for t, v in zip(times, values, strict=True):
            assert t >= last_t, f'times must be a non-decreasing list, but {t} < {last_t}'

            if t > last_t:
                last_t = t
                last_i += 1
                times_unique.append(t)
                values_unique.append(v)
            else:
                if keep_last_update:
                    values_unique[last_i] = v

        return (times_unique, values_unique)

    def uniquePointsCurve(self, keep_last_update=True, copy_curve=False) -> 'Curve':  # noqa: N802
        times_unique, values_unique = self._uniqueTimesValues(self.times(), self.values(), keep_last_update)
        if copy_curve:
            return self.clone(times=times_unique, values=values_unique)

        self.times = times_unique
        self.values = values_unique
        self.reset()
        return self


class TwoFuncInterpolator:
    def __init__(self, in_func, out_func, in_func_on_arrays=None, _interpolator=interpolate.interp1d):
        if in_func:
            in_func_on_arrays = lambda list_x, list_y: [in_func(x, list_y[i]) for i, x in enumerate(list_x)]  # noqa: E731

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
    dates: list = RT()

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
        f = self._to_number
        times = [f(d) for d in value]
        return self.set_value('times', times)

    def beginning_of_time_set(self, trait, d) -> RC:
        t = self._to_number(d)
        self.raw_set_value(trait, t)
        return RC_TRUE

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

    def perturb(self, d: date, new_value, perturb_existing_only=False):
        if perturb_existing_only:
            assert d in self.dates, f'{d} is not in the curve'

        values = self.values
        self.invalidate_value('values')
        self.values = values
        self.update(d, new_value)

    def bracketDateNodes(self, d: date) -> tuple:  # noqa: N802
        t = self._to_number(d)

        times: list = self.times
        last_time = times[-1]
        first_time = times[0]
        if t > last_time:
            return (self._from_number(last_time), None)

        if t < first_time:
            return (None, self._from_number(first_time))

        i = bisect.bisect_left(times, t)
        if times[i] == t:
            d = self._from_number(times[i])
            return (d, d)

        d_left = self._from_number(times[i - 1])
        d_right = self._from_number(times[i])
        return (d_left, d_right)

    def beginning_of_time_as_date(self) -> date:
        return DateCurve._from_number(self.beginning_of_time)

    def dates_values(self, min_date: date = None, max_date: date = None) -> list:
        dates = self.dates
        values = self.values
        return [(d, v) for d, v in zip(dates, values, strict=True) if (not min_date or d >= min_date) and (not max_date or d <= max_date)]
