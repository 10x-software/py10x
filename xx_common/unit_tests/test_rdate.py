from __future__ import annotations

from datetime import date

import pytest
from xx_common.rdate import (
    BIZDAY_ROLL_RULE,
    PROPAGATE_DATES,
    TENOR_FREQUENCY,
    RDate,
)


class TestRDate:
    """Unit tests for RDate class."""

    def test_init_with_symbol(self):
        """Test RDate constructor with symbol strings."""
        # Test basic symbols
        rd = RDate('3M')
        assert rd.freq == TENOR_FREQUENCY.MONTH
        assert rd.count == 3

        rd = RDate('1Y')
        assert rd.freq == TENOR_FREQUENCY.YEAR
        assert rd.count == 1

        rd = RDate('6Q')
        assert rd.freq == TENOR_FREQUENCY.QUARTER
        assert rd.count == 6

        rd = RDate('2W')
        assert rd.freq == TENOR_FREQUENCY.WEEK
        assert rd.count == 2

        rd = RDate('5C')
        assert rd.freq == TENOR_FREQUENCY.CALDAY
        assert rd.count == 5

        # Test negative values
        rd = RDate('-2M')
        assert rd.freq == TENOR_FREQUENCY.MONTH
        assert rd.count == -2

    def test_init_with_freq_and_count(self):
        """Test RDate constructor with frequency and count parameters."""
        rd = RDate(freq=TENOR_FREQUENCY.MONTH, count=3)
        assert rd.freq == TENOR_FREQUENCY.MONTH
        assert rd.count == 3

        # Test default count
        rd = RDate(freq=TENOR_FREQUENCY.YEAR)
        assert rd.freq == TENOR_FREQUENCY.YEAR
        assert rd.count == 1

    def test_init_invalid_symbol(self):
        """Test RDate constructor with invalid symbol raises AttributeError."""
        with pytest.raises(AttributeError, match="Invalid tenor symbol '3X'"):
            RDate('3X')

    def test_init_missing_freq(self):
        """Test RDate constructor without freq parameter raises AssertionError."""
        with pytest.raises(AssertionError, match='freq must be a valid TENOR_FREQUENCY'):
            RDate(count=3)

    def test_symbol(self):
        """Test symbol property returns correct string representation."""
        rd = RDate('3M')
        assert rd.symbol() == '3M'

        rd = RDate('1Y')
        assert rd.symbol() == '1Y'

        rd = RDate('-2Q')
        assert rd.symbol() == '-2Q'

    def test_to_str(self):
        """Test to_str method returns symbol."""
        rd = RDate('5C')
        assert rd.to_str() == '5C'

    def test_serialize_deserialize(self):
        """Test serialization and deserialization."""
        rd = RDate('3M')
        serialized = rd.serialize(embed=True)
        assert serialized == '3M'

        deserialized = RDate.deserialize(serialized)
        assert deserialized.freq == rd.freq
        assert deserialized.count == rd.count

    def test_from_str(self):
        """Test from_str class method."""
        rd = RDate.from_str('2Y')
        assert rd.freq == TENOR_FREQUENCY.YEAR
        assert rd.count == 2

    def test_from_any_xstr(self):
        """Test from_any_xstr class method."""
        # Test with RDate instance
        rd1 = RDate('3M')
        rd2 = RDate.from_any_xstr(rd1)
        assert rd2.freq == rd1.freq
        assert rd2.count == rd1.count

        # Test with tuple
        rd3 = RDate.from_any_xstr((TENOR_FREQUENCY.YEAR, 5))
        assert rd3.freq == TENOR_FREQUENCY.YEAR
        assert rd3.count == 5

        # Test invalid type
        with pytest.raises(AssertionError, match='unexpected type'):
            RDate.from_any_xstr('invalid')

    def test_same_values(self):
        """Test same_values class method."""
        rd1 = RDate('3M')
        rd2 = RDate('3M')
        rd3 = RDate('6M')

        assert RDate.same_values(rd1, rd2) is True
        assert RDate.same_values(rd1, rd3) is False

    def test_apply_basic(self):
        """Test apply method with basic calendar operations."""
        rd = RDate('3M')
        start_date = date(2023, 1, 15)

        # Create a mock calendar that treats all days as business days
        class MockCalendar:
            def is_bizday(self, d):
                return True

            def next_bizday(self, d):
                return d

            def prev_bizday(self, d):
                return d

            def advance_bizdays(self, d, count):
                from datetime import timedelta

                return d + timedelta(days=count)

        cal = MockCalendar()

        # Test with NO_ROLL rule
        result = rd.apply(start_date, cal, BIZDAY_ROLL_RULE.NO_ROLL)
        expected = date(2023, 4, 15)  # 3 months later
        assert result == expected

    def test_apply_bizday(self):
        """Test apply method with business day frequency."""
        rd = RDate(freq=TENOR_FREQUENCY.BIZDAY, count=5)

        class MockCalendar:
            def is_bizday(self, d):
                return True

            def next_bizday(self, d):
                return d

            def prev_bizday(self, d):
                return d

            def advance_bizdays(self, d, count):
                from datetime import timedelta

                return d + timedelta(days=count)

        cal = MockCalendar()

        start_date = date(2023, 1, 15)
        result = rd.apply(start_date, cal, BIZDAY_ROLL_RULE.NO_ROLL)
        expected = date(2023, 1, 20)  # 5 business days later
        assert result == expected

    def test_apply_rule(self):
        """Test apply_rule class method."""
        start_date = date(2023, 1, 15)

        class MockCalendar:
            def is_bizday(self, d):
                return True

            def next_bizday(self, d):
                return d

            def prev_bizday(self, d):
                return d

            def advance_bizdays(self, d, count):
                from datetime import timedelta

                return d + timedelta(days=count)

        cal = MockCalendar()

        # Apply multiple tenors: 3M then 1Y
        result = RDate.apply_rule(start_date, cal, BIZDAY_ROLL_RULE.NO_ROLL, '3M,1Y')
        expected = date(2024, 4, 15)  # 3M from Jan 15 = Apr 15, then 1Y = Apr 15 2024
        assert result == expected

    def test_conversion_freq_multiplier(self):
        """Test conversion_freq_multiplier method."""
        # Same frequency
        rd1 = RDate('3M')
        rd2 = RDate('6M')
        assert rd1.conversion_freq_multiplier(rd2.freq) == 1.0

        # Different frequencies
        rd_year = RDate('1Y')
        rd_month = RDate('12M')
        assert rd_year.conversion_freq_multiplier(rd_month.freq) == 12

        rd_quarter = RDate('1Q')
        assert rd_year.conversion_freq_multiplier(rd_quarter.freq) == 4

        # Invalid conversions
        rd_bizday = RDate(freq=TENOR_FREQUENCY.BIZDAY, count=1)
        with pytest.raises(ValueError, match='cannot convert'):
            rd_year.conversion_freq_multiplier(rd_bizday.freq)

    def test_equate_freq(self):
        """Test equate_freq method."""
        # Same frequency
        rd1 = RDate('3M')
        rd2 = RDate('6M')
        eq1, eq2 = rd1.equate_freq(rd2)
        assert eq1.freq == eq2.freq == TENOR_FREQUENCY.MONTH
        assert eq1.count == 3
        assert eq2.count == 6

        # Different frequencies - convert to common frequency
        rd_year = RDate('1Y')
        rd_month = RDate('12M')
        eq1, eq2 = rd_year.equate_freq(rd_month)
        assert eq1.freq == eq2.freq == TENOR_FREQUENCY.MONTH
        assert eq1.count == 12  # 1Y = 12M
        assert eq2.count == 12

    def test_multadd(self):
        """Test multadd method."""
        rd = RDate('6M')

        # Multiply by scalar
        result = rd.multadd(2.0, 0)
        assert result.freq == TENOR_FREQUENCY.MONTH
        assert result.count == 12

        # Add another RDate
        rd2 = RDate('3M')
        result = rd.multadd(1.0, rd2)
        assert result.freq == TENOR_FREQUENCY.MONTH
        assert result.count == 9

        # Invalid addition
        with pytest.raises(ValueError, match='cannot add a non-zero number'):
            rd.multadd(1.0, 5)

        # Invalid type
        with pytest.raises(ValueError, match='cannot calc a linear combination'):
            rd.multadd(1.0, [])

    def test_mathematical_operations(self):
        """Test mathematical operations (__mul__, __rmul__, __truediv__, __add__)."""
        rd = RDate('6M')

        # Multiplication
        result = rd * 2
        assert result.freq == TENOR_FREQUENCY.MONTH
        assert result.count == 12

        result = 3 * rd
        assert result.freq == TENOR_FREQUENCY.MONTH
        assert result.count == 18

        # Division by scalar
        result = rd / 2
        assert result.freq == TENOR_FREQUENCY.MONTH
        assert result.count == 3

        # Division by another RDate
        rd2 = RDate('3M')
        result = rd / rd2
        assert result == 2.0

        # Addition
        result = rd + rd2
        assert result.freq == TENOR_FREQUENCY.MONTH
        assert result.count == 9

    def test_from_tenors(self):
        """Test from_tenors class method."""
        tenors = RDate.from_tenors('3M,1Y,6Q')
        assert len(tenors) == 3
        assert tenors[0].symbol() == '3M'
        assert tenors[1].symbol() == '1Y'
        assert tenors[2].symbol() == '6Q'

        # Test with custom delimiter
        tenors = RDate.from_tenors('3M;1Y;6Q', delim=';')
        assert len(tenors) == 3

    def test_add_bizdays(self):
        """Test add_bizdays class method."""
        start_date = date(2023, 1, 15)

        class MockCalendar:
            def is_bizday(self, d):
                return True

            def next_bizday(self, d):
                return d

            def prev_bizday(self, d):
                return d

            def advance_bizdays(self, d, count):
                from datetime import timedelta

                return d + timedelta(days=count)

        cal = MockCalendar()

        result = RDate.add_bizdays(start_date, 5, cal, BIZDAY_ROLL_RULE.NO_ROLL)
        expected = date(2023, 1, 20)
        assert result == expected

    def test_roll_to_bizday(self):
        """Test roll_to_bizday class method."""
        test_date = date(2023, 1, 15)

        class MockCalendar:
            def is_bizday(self, d):
                return True

            def next_bizday(self, d):
                return d

            def prev_bizday(self, d):
                return d

        cal = MockCalendar()

        result = RDate.roll_to_bizday(test_date, cal, BIZDAY_ROLL_RULE.NO_ROLL)
        assert result == test_date  # NO_ROLL returns the date as-is

    def test_relop(self):
        """Test relop class method."""
        rd1 = RDate('3M')
        rd2 = RDate('6M')
        test_date = date(2023, 1, 15)

        class MockCalendar:
            def is_bizday(self, d):
                return True

            def next_bizday(self, d):
                return d

            def prev_bizday(self, d):
                return d

        cal = MockCalendar()

        # Test less than
        result = RDate.relop(RDate.RELOP.LT, rd1, rd2, test_date, cal, BIZDAY_ROLL_RULE.NO_ROLL)
        # 3M from Jan 15 = Apr 15, 6M from Jan 15 = Jul 15, so Apr 15 < Jul 15
        assert result is True

        # Test equal
        rd3 = RDate('3M')
        result = RDate.relop(RDate.RELOP.EQ, rd1, rd3, test_date, cal, BIZDAY_ROLL_RULE.NO_ROLL)
        assert result is True

    def test_dates_schedule_forward(self):
        """Test dates_schedule method with forward propagation."""
        rd = RDate('3M')
        start_date = date(2023, 1, 15)
        end_date = date(2023, 7, 15)

        class MockCalendar:
            def is_bizday(self, d):
                return True

            def next_bizday(self, d):
                return d

            def prev_bizday(self, d):
                return d

        cal = MockCalendar()

        dates = rd.dates_schedule(start_date, end_date, cal, BIZDAY_ROLL_RULE.NO_ROLL, PROPAGATE_DATES.FORWARD, allow_stub=True)

        # Should generate dates: Jan 15, Apr 15, Jul 15
        expected = [date(2023, 1, 15), date(2023, 4, 15), date(2023, 7, 15)]
        assert dates == expected

    def test_dates_schedule_backward(self):
        """Test dates_schedule method with backward propagation."""
        rd = RDate('3M')
        start_date = date(2023, 1, 15)
        end_date = date(2023, 7, 15)

        class MockCalendar:
            def is_bizday(self, d):
                return True

            def next_bizday(self, d):
                return d

            def prev_bizday(self, d):
                return d

        cal = MockCalendar()

        dates = rd.dates_schedule(start_date, end_date, cal, BIZDAY_ROLL_RULE.NO_ROLL, PROPAGATE_DATES.BACKWARD, allow_stub=True)

        # Should generate dates: Jul 15, Apr 15, Jan 15 (backward from end)
        expected = [date(2023, 1, 15), date(2023, 4, 15), date(2023, 7, 15)]
        assert dates == expected

    def test_period_dates(self):
        """Test period_dates method."""
        rd = RDate('3M')
        start_date = date(2023, 1, 15)
        end_date = date(2023, 7, 15)

        class MockCalendar:
            def is_bizday(self, d):
                return True

            def next_bizday(self, d):
                return d

            def prev_bizday(self, d):
                return d

        cal = MockCalendar()

        start_dates, end_dates, all_dates = rd.period_dates(
            start_date, end_date, cal, BIZDAY_ROLL_RULE.NO_ROLL, PROPAGATE_DATES.FORWARD, allow_stub=True
        )

        expected_all = [date(2023, 1, 15), date(2023, 4, 15), date(2023, 7, 15)]
        expected_starts = [date(2023, 1, 15), date(2023, 4, 15)]
        expected_ends = [date(2023, 4, 15), date(2023, 7, 15)]

        assert all_dates == expected_all
        assert start_dates == expected_starts
        assert end_dates == expected_ends

    def test_period_dates_for_tenor(self):
        """Test period_dates_for_tenor method."""
        rd = RDate('3M')  # frequency
        tenor = RDate('9M')  # total tenor
        start_date = date(2023, 1, 15)

        class MockCalendar:
            def is_bizday(self, d):
                return True

            def next_bizday(self, d):
                return d

            def prev_bizday(self, d):
                return d

        cal = MockCalendar()

        start_dates, end_dates, all_dates = rd.period_dates_for_tenor(
            start_date, tenor, cal, BIZDAY_ROLL_RULE.NO_ROLL, PROPAGATE_DATES.FORWARD, allow_stub=True
        )

        # Start at Jan 15, end at Oct 15 (9M later), with 3M periods
        expected_all = [date(2023, 1, 15), date(2023, 4, 15), date(2023, 7, 15), date(2023, 10, 15)]
        expected_starts = [date(2023, 1, 15), date(2023, 4, 15), date(2023, 7, 15)]
        expected_ends = [date(2023, 4, 15), date(2023, 7, 15), date(2023, 10, 15)]

        assert all_dates == expected_all
        assert start_dates == expected_starts
        assert end_dates == expected_ends
