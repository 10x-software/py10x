from __future__ import annotations

from collections import deque
from datetime import date, timedelta

from core_10x.traitable import RT, T, Traitable


class CalendarNameParser:
    """
    calendar_name           := just_name | operation_repr_list
    operation_repr_list     := operation_repr | operation_repr OP_CHAR operation_repr_list
    operation_repr          := op num_args | name_list op num_args
    name_list               := just_name MORE_CHAR just_name MORE_CHAR | just_name MORE_CHAR name_list
    op                      := OR_CHAR | AND_CHAR
    """

    # fmt: off
    MORE_CHAR   = ','
    OR_CHAR     = '|'
    AND_CHAR    = '&'
    OP_CHAR     = '\n'

    s_ops = {
        OR_CHAR:    set.update,
        AND_CHAR:   set.intersection_update
    }
    # fmt: on

    @classmethod
    def combo_name(cls, name: str) -> bool:
        return any(sym in name for sym in cls.s_ops.keys())

    @classmethod
    def operation_repr(cls, calendar_cls, op_char: str, *calendars) -> str:
        assert len(calendars) > 1, 'there must be at least 2 calendars'
        assert op_char in cls.s_ops, f'Unknown op char = {op_char}'

        cal_names = []
        for cal_or_name in calendars:
            if isinstance(cal_or_name, calendar_cls):
                cname = cal_or_name.name
            elif isinstance(cal_or_name, str):
                cal = calendar_cls.existing_instance(name=cal_or_name)
                assert cal, f"Unknown calendar '{cal_or_name}'"
                cname = cal_or_name
            else:
                raise NameError(f"Invalid calendar/name '{cal_or_name}'")

            cal_names.append(cname)

        return f'{cls.MORE_CHAR.join(sorted(cal_names))}{cls.MORE_CHAR}{op_char}{len(cal_names)}{cls.OP_CHAR}'

    def __init__(self):
        self.stack = deque()
        self.non_working_days = set()

    @classmethod
    def parse(cls, calendar_cls, name: str) -> set:
        parser = cls()
        non_working_days = parser.non_working_days
        stack = parser.stack

        operation_repr_list = name.split(cls.OP_CHAR)
        if len(operation_repr_list) == 1:  # -- regular (stored) calendar
            cal = calendar_cls.existing_instance(name=name)
            return cal._non_working_days

        for operation_repr in operation_repr_list:
            if not operation_repr:
                continue

            name_list_op_num_args = operation_repr.split(cls.MORE_CHAR)
            if len(name_list_op_num_args) > 1:  # -- name list followed by op with num_args
                for cname in name_list_op_num_args[:-1]:
                    if cname:
                        cal = calendar_cls.existing_instance(name=cname)
                        assert cal, f"Unknown calendar '{cname}"
                        stack.append(cal._non_working_days)

            op_with_num_args = name_list_op_num_args[-1]
            op_char = op_with_num_args[0]
            op = cls.s_ops.get(op_char)
            assert op, f'Unknown op char {op_char}'
            try:
                num_args = int(op_with_num_args[1:])
            except Exception as e:
                raise RuntimeError(f'Invalid num_args = {op_with_num_args[1:]}') from e

            for _ in range(num_args):
                _non_working_days = stack.pop()
                assert isinstance(_non_working_days, set)

                if not non_working_days:
                    non_working_days.update(_non_working_days)
                else:
                    op(non_working_days, _non_working_days)

            stack.append(non_working_days)  # -- push set of non_working_days of an intermediate calendar

        return non_working_days


class CalendarAdjustment(Traitable):
    name: str           = T(T.ID)
    add_days: list      = T()
    remove_days: list   = T()


#-- TODO: _default_cache = True!
class Calendar(Traitable):
    name: str               = T(T.ID)
    adjusted_for: str       = T(T.ID,   default = '')   // 'Name of a specific adjustment to this calendar, if any'
    description: str        = T()                       // 'Calendar Description'
    non_working_days: list  = T()                       // 'Non-Working Days'

    _non_working_days: set  = RT()

    @classmethod
    def AND(cls, *calendars) -> Calendar:  # noqa: N802
        if not calendars:
            return None

        name = CalendarNameParser.operation_repr(cls, CalendarNameParser.AND_CHAR, *calendars)
        return cls(name=name)

    intersection = AND

    @classmethod
    def OR(cls, *calendars) -> Calendar:  # noqa: N802
        if not calendars:
            return None

        name = CalendarNameParser.operation_repr(cls, CalendarNameParser.OR_CHAR, *calendars)
        return cls(name=name)

    @classmethod
    def union(cls, *calendars) -> Calendar:
        if len(calendars) > 1:
            return cls.OR(*calendars)
        assert calendars, 'At least one calendar is required for union()'
        return cls(name=calendars[0])

    def non_working_days_get(self) -> list:
        non_working_days = CalendarNameParser.parse(self.__class__, self.name)
        adjusted_for = self.adjusted_for
        if adjusted_for:
            ca = CalendarAdjustment.existing_instance_by_id(_id_value=adjusted_for, _throw=False)
            if ca:
                self.add_days(non_working_days, *ca.add_days)
                self.remove_days(non_working_days, *ca.remove_days)

        return sorted(non_working_days) if non_working_days else []

    def _non_working_days_get(self) -> set:
        return set(self.non_working_days)

    @classmethod
    def add_days(cls, days: set, *days_to_add) -> bool:
        if not days_to_add:
            return False

        all_dates = all(type(hd) is date for hd in days_to_add)
        if not all_dates:
            raise TypeError('Every day to add must be a date')

        ndays = len(days)
        days.update(days_to_add)
        return len(days) > ndays

    @classmethod
    def remove_days(cls, days: set, *days_to_remove) -> bool:
        if not days_to_remove:
            return False

        all_dates = all(type(hd) is date for hd in days_to_remove)
        if not all_dates:
            raise TypeError('Every day to remove must be a date')

        ndays = len(days)
        days.difference_update(days_to_remove)
        return len(days) < ndays

    def add_non_working_days(self, *days_to_add):
        non_working_days = set(self.non_working_days)
        if self.add_days(non_working_days, *days_to_add):
            self.non_working_days = list(non_working_days)

    def remove_non_working_days(self, *days_to_remove):
        non_working_days = set(self.non_working_days)
        if self.remove_days(non_working_days, *days_to_remove):
            self.non_working_days = list(non_working_days)

    def is_bizday(self, d: date) -> bool:
        return d not in self._non_working_days

    def next_bizday(self, d: date) -> date:
        dt = timedelta(days=1)
        d += dt
        while not self.is_bizday(d):
            d += dt

        return d

    def prev_bizday(self, d: date) -> date:
        dt = timedelta(days=-1)
        d += dt
        while not self.is_bizday(d):
            d += dt

        return d  # -- TODO: if the cal has ALL days as holidays... :-)

    def advance_bizdays(self, d: date, biz_days: int) -> date:
        if not biz_days:
            return d

        if biz_days > 0:
            for _ in range(biz_days):
                d = self.next_bizday(d)
        else:
            for _ in range(-biz_days):
                d = self.prev_bizday(d)

        return d
