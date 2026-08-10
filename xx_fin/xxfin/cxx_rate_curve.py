from __future__ import annotations

from datetime import date

from cxxfin import BRateCurve as _BRateCurve

from xxfin.py_rate_curve import RateCurve as _PyRateCurve

class RateCurve(_PyRateCurve):
    def accrual(self, d: date, today: date = None) -> float:
        return _BRateCurve.accrual(self, d, today)

    def accrual_fwd(self, d1: date, d2: date, today: date = None) -> float:
        return _BRateCurve.accrual_fwd(self, d1, d2, today)

    def discount_factor(self, d: date, today: date = None) -> float:
        return _BRateCurve.discount_factor(self, d, today)

    def discount_factor_fwd(self, d1, d2, today: date = None) -> float:
        return _BRateCurve.discount_factor_fwd(self, d1, d2, today)
