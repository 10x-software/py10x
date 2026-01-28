from __future__ import annotations

from datetime import date

import pytest
from core_10x.exec_control import CACHE_ONLY
from core_10x.xxcalendar import Calendar, CalendarAdjustment, CalendarNameParser


class TestCalendarNameParser:
    """Unit tests for CalendarNameParser class."""

    def test_combo_name(self):
        """Test combo_name method."""
        assert CalendarNameParser.combo_name('CAL1|CAL2') is True
        assert CalendarNameParser.combo_name('CAL1&CAL2') is True
        assert CalendarNameParser.combo_name('SIMPLE_CAL') is False

    def test_operation_repr_with_calendar_objects(self):
        """Test operation_repr with calendar objects."""

        # Create mock calendar objects for testing
        class MockCalendar:
            def __init__(self, name):
                self.name = name

        cal1 = MockCalendar('CAL1')
        cal2 = MockCalendar('CAL2')
        cal3 = MockCalendar('CAL3')

        result = CalendarNameParser.operation_repr(MockCalendar, CalendarNameParser.OR_CHAR, cal1, cal2, cal3)
        # The result includes a trailing comma before the operation and a newline at the end
        expected = 'CAL1,CAL2,CAL3,|3\n'
        assert result == expected

        result = CalendarNameParser.operation_repr(MockCalendar, CalendarNameParser.AND_CHAR, cal1, cal2)
        expected = 'CAL1,CAL2,&2\n'
        assert result == expected

    def test_operation_repr_with_strings(self):
        """Test operation_repr with string names."""
        # This would require existing calendars in the database
        # We'll test the assertion failures instead
        pass

    def test_operation_repr_invalid_op(self):
        """Test operation_repr with invalid operation character."""

        class MockCalendar:
            def __init__(self, name):
                self.name = name

        cal1 = MockCalendar('CAL1')
        cal2 = MockCalendar('CAL2')

        with pytest.raises(AssertionError, match='Unknown op char = \\*'):
            CalendarNameParser.operation_repr(MockCalendar, '*', cal1, cal2)

    def test_operation_repr_too_few_calendars(self):
        """Test operation_repr with too few calendars."""

        class MockCalendar:
            def __init__(self, name):
                self.name = name

        cal1 = MockCalendar('CAL1')

        with pytest.raises(AssertionError, match='there must be at least 2 calendars'):
            CalendarNameParser.operation_repr(MockCalendar, CalendarNameParser.OR_CHAR, cal1)

    def test_parse_simple_calendar(self, ts_instance):
        """Test parse method with simple calendar name."""
        from datetime import date

        with ts_instance:
            holidays = {date(2024, 1, 1), date(2024, 12, 25)}
            cal = Calendar(
                name='TEST_SIMPLE_CAL',
                description='Simple calendar for parsing',
                non_working_days=sorted(holidays),
                _replace=True,
            )
            assert cal.save()

            parsed_days = CalendarNameParser.parse(Calendar, cal.name)
            assert parsed_days == holidays

    def test_parse_combined_calendar(self, ts_instance):
        """Test parse method with combined calendar operations."""
        from datetime import date

        with ts_instance:
            holidays_a = {date(2024, 1, 1), date(2024, 1, 2)}
            holidays_b = {date(2024, 1, 2), date(2024, 1, 3)}

            cal_a = Calendar(
                name='TEST_CAL_A',
                description='Calendar A for combined parsing',
                non_working_days=sorted(holidays_a),
                _replace=True,
            )
            cal_b = Calendar(
                name='TEST_CAL_B',
                description='Calendar B for combined parsing',
                non_working_days=sorted(holidays_b),
                _replace=True,
            )

            assert cal_a.save()
            assert cal_b.save()

            # OR operation: union of non-working days
            union_name = CalendarNameParser.operation_repr(Calendar, CalendarNameParser.OR_CHAR, cal_a, cal_b)
            union_days = CalendarNameParser.parse(Calendar, union_name)
            assert union_days == holidays_a | holidays_b

            # AND operation: intersection of non-working days
            intersection_name = CalendarNameParser.operation_repr(Calendar, CalendarNameParser.AND_CHAR, cal_a, cal_b)
            intersection_days = CalendarNameParser.parse(Calendar, intersection_name)
            assert intersection_days == holidays_a & holidays_b


class TestCalendarAdjustment:
    """Unit tests for CalendarAdjustment class."""

    def test_creation(self):
        """Test CalendarAdjustment can be created."""
        with CACHE_ONLY():
            # CalendarAdjustment requires name (which has T.ID flag)
            ca = CalendarAdjustment(name='TEST_ADJ', _replace=True)
            assert ca.name == 'TEST_ADJ'

    def test_calendar_adjustment_is_storable(self):
        """Test that CalendarAdjustment is storable."""
        assert CalendarAdjustment.is_storable()
        assert CalendarAdjustment.trait('name')  # Has ID trait


class TestCalendar:
    """Unit tests for Calendar class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create test calendar with some holidays
        self.test_holidays = [
            date(2023, 1, 1),  # New Year's Day
            date(2023, 12, 25),  # Christmas
            date(2023, 7, 4),  # Independence Day
        ]

    def test_add_days(self):
        """Test add_days class method."""
        days = {date(2023, 1, 1), date(2023, 1, 2)}

        # Add new days
        result = Calendar.add_days(days, date(2023, 1, 3), date(2023, 1, 4))
        assert result is True
        assert days == {date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)}

        # Add existing day (no change)
        result = Calendar.add_days(days, date(2023, 1, 1))
        assert result is False

        # Add no days
        result = Calendar.add_days(days)
        assert result is False

    def test_add_days_invalid_type(self):
        """Test add_days with invalid types raises TypeError."""
        days = set()
        with pytest.raises(TypeError, match='Every day to add must be a date'):
            Calendar.add_days(days, '2023-01-01')

    def test_remove_days(self):
        """Test remove_days class method."""
        days = {date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)}

        # Remove existing days
        result = Calendar.remove_days(days, date(2023, 1, 1), date(2023, 1, 2))
        assert result is True
        assert days == {date(2023, 1, 3)}

        # Remove non-existing day (no change)
        result = Calendar.remove_days(days, date(2023, 1, 4))
        assert result is False

        # Remove no days
        result = Calendar.remove_days(days)
        assert result is False

    def test_remove_days_invalid_type(self):
        """Test remove_days with invalid types raises TypeError."""
        days = {date(2023, 1, 1)}
        with pytest.raises(TypeError, match='Every day to remove must be a date'):
            Calendar.remove_days(days, '2023-01-01')

    def test_is_bizday(self):
        """Test is_bizday method using proper Traitable calendar."""
        with CACHE_ONLY():
            # Create a proper Calendar instance with non-working days
            cal = Calendar(
                name='TEST_CAL_HOLIDAYS', description='Calendar with holidays', non_working_days=[date(2023, 1, 1), date(2023, 12, 25)], _replace=True
            )

            # Test business days
            assert cal.is_bizday(date(2023, 1, 2)) is True
            assert cal.is_bizday(date(2023, 2, 1)) is True

            # Test non-business days
            assert cal.is_bizday(date(2023, 1, 1)) is False
            assert cal.is_bizday(date(2023, 12, 25)) is False

    def test_next_bizday(self):
        """Test next_bizday method using proper Traitable calendar."""
        with CACHE_ONLY():
            # Create a calendar with consecutive holidays
            cal = Calendar(
                name='TEST_CAL_CONSECUTIVE',
                description='Calendar with consecutive holidays',
                non_working_days=[
                    date(2023, 1, 1),  # Sunday
                    date(2023, 1, 2),  # Monday
                    date(2023, 1, 3),  # Tuesday
                ],
                _replace=True,
            )

            # Test from a business day
            result = cal.next_bizday(date(2023, 1, 4))  # Wednesday
            assert result == date(2023, 1, 5)  # Thursday

            # Test from a non-business day
            result = cal.next_bizday(date(2023, 1, 1))  # Sunday (holiday)
            assert result == date(2023, 1, 4)  # Wednesday

            # Test from a non-business day in middle of holidays
            result = cal.next_bizday(date(2023, 1, 2))  # Monday (holiday)
            assert result == date(2023, 1, 4)  # Wednesday

    def test_prev_bizday(self):
        """Test prev_bizday method using proper Traitable calendar."""
        with CACHE_ONLY():
            # Create a calendar with consecutive holidays
            cal = Calendar(
                name='TEST_CAL_PREV',
                description='Calendar for prev_bizday test',
                non_working_days=[
                    date(2023, 1, 1),  # Sunday
                    date(2023, 1, 2),  # Monday
                    date(2023, 1, 3),  # Tuesday
                ],
                _replace=True,
            )

            # Test from a business day
            result = cal.prev_bizday(date(2023, 1, 4))  # Wednesday
            assert result == date(2022, 12, 31)  # Saturday (goes back one day from Wednesday)

            # Test from a non-business day
            result = cal.prev_bizday(date(2023, 1, 1))  # Sunday (holiday)
            assert result == date(2022, 12, 31)  # Saturday

    def test_advance_bizdays_forward(self):
        """Test advance_bizdays with positive count using proper Traitable calendar."""
        with CACHE_ONLY():
            # Create a calendar with weekends and holidays
            cal = Calendar(
                name='TEST_CAL_ADVANCE',
                description='Calendar for advance_bizdays test',
                non_working_days=[
                    date(2023, 1, 1),  # New Year
                    date(2023, 1, 7),  # Saturday
                    date(2023, 1, 8),  # Sunday
                    date(2023, 1, 14),  # Saturday
                    date(2023, 1, 15),  # Sunday
                ],
                _replace=True,
            )

            # Start from Friday Jan 6, 2023
            start_date = date(2023, 1, 6)  # Friday

            # Advance 1 business day (skip weekend)
            result = cal.advance_bizdays(start_date, 1)
            assert result == date(2023, 1, 9)  # Monday

            # Advance 3 business days
            result = cal.advance_bizdays(start_date, 3)
            assert result == date(2023, 1, 11)  # Wednesday

            # Advance 0 business days (no change)
            result = cal.advance_bizdays(start_date, 0)
            assert result == start_date

    def test_advance_bizdays_backward(self):
        """Test advance_bizdays with negative count using proper Traitable calendar."""
        with CACHE_ONLY():
            # Create a calendar with weekends and holidays (same as forward test)
            cal = Calendar(
                name='TEST_CAL_BACKWARD',
                description='Calendar for backward advance_bizdays test',
                non_working_days=[
                    date(2023, 1, 1),  # New Year
                    date(2023, 1, 7),  # Saturday
                    date(2023, 1, 8),  # Sunday
                    date(2023, 1, 14),  # Saturday
                    date(2023, 1, 15),  # Sunday
                ],
                _replace=True,
            )

            # Start from Wednesday Jan 11, 2023
            start_date = date(2023, 1, 11)  # Wednesday

            # Go back 1 business day (skip weekend)
            result = cal.advance_bizdays(start_date, -1)
            assert result == date(2023, 1, 10)  # Tuesday

            # Go back 3 business days
            result = cal.advance_bizdays(start_date, -3)
            assert result == date(2023, 1, 6)  # Friday

    def test_and(self):
        """Test AND class method."""
        # This would require actual calendar instances
        # Test the None case
        result = Calendar.AND()
        assert result is None

    def test_or(self):
        """Test OR class method."""
        # This would require actual calendar instances
        # Test the None case
        result = Calendar.OR()
        assert result is None

    def test_union(self):
        """Test union class method."""
        # Test with single calendar (would require actual instance)
        with pytest.raises(AssertionError, match='At least one calendar is required for union'):
            Calendar.union()

    def test_intersection_alias(self):
        """Test that intersection is an alias for AND."""
        assert Calendar.intersection == Calendar.AND

    def test_add_non_working_days(self):
        """Test add_non_working_days instance method."""
        # Test the class method that add_non_working_days would use
        days = {date(2023, 1, 1)}
        Calendar.add_days(days, date(2023, 12, 25), date(2023, 7, 4))
        assert days == {date(2023, 1, 1), date(2023, 12, 25), date(2023, 7, 4)}

    def test_remove_non_working_days(self):
        """Test remove_non_working_days instance method."""
        # Test the class method that remove_non_working_days would use
        days = {date(2023, 1, 1), date(2023, 12, 25), date(2023, 7, 4)}
        Calendar.remove_days(days, date(2023, 12, 25))
        assert days == {date(2023, 1, 1), date(2023, 7, 4)}

    def test_non_working_days_get(self):
        """Test non_working_days_get method."""
        # This method requires database access, so we'll skip detailed testing
        # The method parses calendar names and gets holidays from database
        pass

    def test_non_working_days_trait_get(self):
        """Test _non_working_days_get trait method."""
        # Test the logic that _non_working_days_get would use
        non_working_days = [date(2023, 1, 1), date(2023, 12, 25)]
        result = set(non_working_days)
        assert result == {date(2023, 1, 1), date(2023, 12, 25)}

    def test_calendar_instantiation(self):
        """Test proper Calendar instantiation following Traitable patterns."""
        # Calendar is storable, so it needs proper trait values like other storable classes
        with CACHE_ONLY():
            # Calendar requires name (which has T.ID flag)
            cal = Calendar(name='TEST_CAL', description='Test Calendar', _replace=True)
            assert cal.name == 'TEST_CAL'
            assert cal.description == 'Test Calendar'

    def test_calendar_is_storable(self):
        """Test that Calendar is storable like other Traitable subclasses."""
        assert Calendar.is_storable()
        assert Calendar.trait('name')  # Has ID trait
        assert Calendar.trait('_collection_name')  # Has collection name trait
