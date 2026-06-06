USE_BCURVE = False
#USE_BCURVE = True

if not USE_BCURVE:
    from xx_common.py_curve import Curve, DateCurve, IP_KIND, CurveParams

else:
    from xx_common.cxx_curve import Curve, DateCurve, IP_KIND, CurveParams