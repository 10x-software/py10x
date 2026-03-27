"""Unit tests for core_10x/xinf.py."""

import math
import sys

import pytest

from core_10x.xinf import XInf


# ---------------------------------------------------------------------------
# Comparisons — positive infinity
# ---------------------------------------------------------------------------


class TestXInfComparisons:
    def test_greater_than_large_number(self):
        assert XInf > 1e300

    def test_greater_than_zero(self):
        assert XInf > 0

    def test_greater_than_negative(self):
        assert XInf > -1e300

    def test_equal_to_itself(self):
        assert XInf == XInf

    def test_not_equal_to_number(self):
        assert XInf != 1e300

    def test_ge_itself(self):
        assert XInf >= XInf

    def test_not_lt_any_number(self):
        assert not (XInf < 1e300)

    def test_not_lt_itself(self):
        assert not (XInf < XInf)

    def test_le_itself(self):
        assert XInf <= XInf

    def test_not_le_number(self):
        assert not (XInf <= 1e300)


# ---------------------------------------------------------------------------
# Comparisons — negative infinity  (-XInf)
# ---------------------------------------------------------------------------


class TestNegXInfComparisons:
    def test_less_than_large_negative(self):
        assert -XInf < -1e300

    def test_less_than_zero(self):
        assert -XInf < 0

    def test_less_than_large_positive(self):
        assert -XInf < 1e300

    def test_equal_to_itself(self):
        assert -XInf == -XInf

    def test_not_equal_to_xinf(self):
        assert -XInf != XInf

    def test_not_equal_to_number(self):
        assert -XInf != -1e300

    def test_le_itself(self):
        assert -XInf <= -XInf

    def test_le_any_number(self):
        assert -XInf <= -1e300

    def test_not_gt_any_number(self):
        assert not (-XInf > -1e300)

    def test_not_gt_itself(self):
        assert not (-XInf > -XInf)

    def test_ge_itself(self):
        assert -XInf >= -XInf

    def test_not_ge_number(self):
        assert not (-XInf >= 0)


# ---------------------------------------------------------------------------
# Invert / identity
# ---------------------------------------------------------------------------


class TestXInfInvert:
    def test_invert_xinf_is_neg_xinf(self):
        assert ~XInf is -XInf

    def test_invert_neg_xinf_is_xinf(self):
        assert ~(-XInf) is XInf

    def test_neg_neg_xinf_is_xinf(self):
        ninf = -XInf
        assert -ninf is XInf

    def test_neg_xinf_is_same_object_each_time(self):
        """Negative infinity is a stable singleton."""
        a = -XInf
        b = -XInf
        assert a is b


# ---------------------------------------------------------------------------
# Arithmetic — positive infinity
# ---------------------------------------------------------------------------


class TestXInfArithmetic:
    def test_add_number_is_xinf(self):
        assert XInf + 5 is XInf

    def test_sub_number_is_xinf(self):
        assert XInf - 5 is XInf

    def test_sub_xinf_is_xinf(self):
        assert XInf - XInf is XInf

    def test_mul_is_xinf(self):
        assert XInf * 2 is XInf

    def test_div_is_xinf(self):
        assert XInf / 2 is XInf

    def test_floordiv_is_xinf(self):
        assert XInf // 2 is XInf

    def test_pow_is_xinf(self):
        assert XInf**2 is XInf

    def test_abs_is_xinf(self):
        assert abs(XInf) is XInf


# ---------------------------------------------------------------------------
# Arithmetic — negative infinity
# ---------------------------------------------------------------------------


class TestNegXInfArithmetic:
    def test_add_is_neg_xinf(self):
        assert -XInf + 5 is -XInf

    def test_sub_is_neg_xinf(self):
        assert -XInf - 5 is -XInf

    def test_mul_is_neg_xinf(self):
        assert -XInf * 2 is -XInf

    def test_div_is_neg_xinf(self):
        assert -XInf / 2 is -XInf

    def test_abs_is_xinf(self):
        assert abs(-XInf) is XInf

    def test_neg_is_xinf(self):
        ninf = -XInf
        assert -(ninf) is XInf


# ---------------------------------------------------------------------------
# Type conversions
# ---------------------------------------------------------------------------


class TestXInfConversions:
    def test_float_is_inf(self):
        assert float(XInf) == math.inf

    def test_int_is_maxsize(self):
        assert int(XInf) == sys.maxsize

    def test_bool_is_true(self):
        assert bool(XInf)

    def test_float_neg_is_neg_inf(self):
        assert float(-XInf) == -math.inf

    def test_int_neg_is_min(self):
        assert int(-XInf) == ~sys.maxsize

    def test_repr_is_infinity_symbol(self):
        assert repr(XInf) == '∞'

    def test_repr_neg_is_minus_infinity(self):
        assert repr(-XInf) == '-∞'


# ---------------------------------------------------------------------------
# Subclassing is forbidden
# ---------------------------------------------------------------------------


class TestXInfSubclassing:
    def test_cannot_subclass_pinf_type(self):
        from core_10x.xinf import PInfType

        with pytest.raises(TypeError, match='May not derive from Inf'):

            class Bad(PInfType):
                pass

    def test_cannot_subclass_minf_type(self):
        from core_10x.xinf import MInfType

        with pytest.raises(TypeError, match='May not derive from Inf'):

            class Bad(MInfType):
                pass
