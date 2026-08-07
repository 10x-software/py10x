from datetime import date

import pytest

from xxcommon.cxx_curve import DateCurve as CxxDateCurve
from xxcommon.py_curve import DateCurve as PyDateCurve


class TestDateCurve:
    def setup_method(self):
        self.d1 = date(2019, 12, 31)
        self.d2 = date(2020, 12, 31)
        self.r1 = 0.1
        self.r2 = 0.2

        self.dates = [self.d1, self.d2]
        self.values = [self.r1, self.r2]

        self.d05 = self.d1 + (self.d2 - self.d1) / 2
        self.r05 = (self.r1 + self.r2) / 2

    @pytest.mark.parametrize('curve_class', [PyDateCurve, CxxDateCurve], ids=['py', 'cxx'])
    def test_py_curve_dates(self, curve_class):
        dc = curve_class(dates=self.dates, values=self.values)
        for d, r in zip(self.dates, self.values, strict=True):
            assert dc.value(d) == pytest.approx(r)  # add assertion here

        assert dc.value(self.d05) == pytest.approx(self.r05)  # add assertion here
