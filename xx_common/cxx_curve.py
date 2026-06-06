from datetime import date

from py10x_kernel import BCurve, BDateCurve, IPKind as IP_KIND
from core_10x.traitable import Any, RC, RC_TRUE, RT, AnonymousTraitable, T, Traitable


class CurveParams(Traitable):
    #DEFAULT_INTERPOLATOR = interpolate.interp1d

    #interpolator: Any   = RT()
    ip_kind: IP_KIND    = RT(IP_KIND.LINEAR)
    #assume_sorted: bool = RT(True)
    #copy: bool          = RT(False)
    fill_value: Any     = RT('extrapolate')     ## it's 'extrapolate' or a tuple (left_value, right_value) for extrapolation
    #bounds_error: bool  = RT(False)

    #def interpolator_get(self):     return self.__class__.DEFAULT_INTERPOLATOR

class Curve(AnonymousTraitable, BCurve):
    beginning_of_time: float  = T(None)

#class DateCurve(AnonymousTraitable, BDateCurve):
class DateCurve(AnonymousTraitable):
    params: CurveParams     = RT()
    bcurve: BDateCurve      = RT(T.STICKY)
    dates: list             = RT()

    times: list             = T()
    values: list            = T()
    beginning_of_time: int  = T(None)

    def bcurve_get(self) -> BDateCurve:
        print('bcurve_get')
        return BDateCurve()

    def times_get(self) -> list:
        return self.bcurve.times

    def values_get(self) -> list:
        return self.bcurve.values

    def times_set(self, t, times) -> RC:
        self.bcurve.set_times(times)
        return RC_TRUE

    def values_set(self, t, values) -> RC:
        self.bcurve.set_values(values)
        return RC_TRUE

    def params_get(self) -> CurveParams:
        return CurveParams()

    def start_time(self) -> date:
        return self.bcurve.start_time()

    def end_time(self) -> date:
        return self.bcurve.end_time()

    def update(self, d: date, value, reset = True):
        self.bcurve.update(d, value)
        if reset:
            self.reset()

    def reset(self):
        self.invalidate_value('dates')

    def value(self, d: date) -> float:
        return self.bcurve.value(d)

    def remove(self, d: date, reset = True):
        if self.bcurve.remove(d):
            self.invalidate_value('dates')

    def dates_values(self, min_date: date = None, max_date: date = None) -> list:
        dates = self.dates
        values = self.values
        return [(d, v) for d, v in zip(dates, values, strict=True) if (not min_date or d >= min_date) and (not max_date or d <= max_date)]

    def update_many(self, times, values, reset = True):
        assert len(times) == len(values), 'times and values size mismatch'
        bcurve = self.bcurve
        for i, t in enumerate(times):
            bcurve.update(t, values[i])

        if reset:
            self.reset()

    def set_curve_params(self, **param_values) -> RC:
        params = self.params
        rc = params.set_values(**param_values)
        if rc:
            self.bcurve.set_ip_kind(params.ip_kind)
            fill = params.fill_value
            if isinstance(fill, tuple):
                self.bcurve.set_flat(fill[0], fill[1])
            else:
                self.bcurve.set_linear()

        self.reset()
        return rc

    def set_curve_params_to_extrapolate(self) -> RC:
        return self.set_curve_params(bounds_error = False, fill_value = 'extrapolate')

    ## extrapolate flat left (by the first value) and right (by last value)
    def set_curve_params_to_flat_extrapolate(self) -> RC:
        values = self.values
        return self.set_curve_params(bounds_error = False, fill_value = (values[0], values[-1]))

    def values_at(self, dates) -> tuple:
        return tuple(self.value(d) for d in dates)

    @classmethod
    def same_values(cls, v1, v2) -> bool:
        if v1.id() == v2.id():
            return True

        return v1.times == v2.times and v1.values == v2.values


