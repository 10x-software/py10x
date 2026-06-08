USE_BCURVE = False
#USE_BCURVE = True

if not USE_BCURVE:
    from xx_common.py_curve import Curve, DateCurve, IP_KIND, CurveParams
else:
    from xx_common.cxx_curve import Curve, DateCurve, IP_KIND, CurveParams

from scipy import interpolate

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