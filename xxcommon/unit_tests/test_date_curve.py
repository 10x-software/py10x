import unittest
from datetime import date

class TestDateCurve(unittest.TestCase):
    def setUp(self):
        self.d1 = date(2019, 12, 31)
        self.d2 = date(2020, 12, 31)
        self.r1 = 0.1
        self.r2 = 0.2

        self.dates  = [self.d1, self.d2]
        self.values = [self.r1, self.r2]

        self.d05 = self.d1 + (self.d2 - self.d1) / 2
        self.r05 = (self.r1 + self.r2) / 2

    def test_py_curve_dates(self):
        from xxcommon.py_curve import DateCurve
        dc = DateCurve(dates = self.dates, values = self.values)
        for d, r in zip(self.dates, self.values):
            self.assertAlmostEqual(dc.value(d), r)  # add assertion here

        self.assertAlmostEqual(dc.value(self.d05), self.r05)  # add assertion here

    def test_cxx_curve_dates(self):
        from xxcommon.cxx_curve import DateCurve
        dc = DateCurve(dates=self.dates, values=self.values)
        for d, r in zip(self.dates, self.values):
            self.assertAlmostEqual(dc.value(d), r)  # add assertion here

        self.assertAlmostEqual(dc.value(self.d05), self.r05)  # add assertion here


if __name__ == '__main__':
    unittest.main()
