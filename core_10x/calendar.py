from datetime import date, timedelta
from collections import deque
from operator import le, lt
from typing import Iterable

from core_10x.traitable import Traitable, T, RT, Ui, RC

class CalendarNameParser:
    """
    calendar_name           := just_name | operation_repr_list
    operation_repr_list     := operation_repr | operation_repr OP_CHAR operation_repr_list
    operation_repr          := op num_args | name_list op num_args
    name_list               := just_name MORE_CHAR just_name MORE_CHAR | just_name MORE_CHAR name_list
    op                      := OR_CHAR | AND_CHAR
    """
    MORE_CHAR   = ','
    OR_CHAR     = '|'
    AND_CHAR    = '&'
    OP_CHAR     = '\n'

    s_ops = {
        OR_CHAR:    set.update,
        AND_CHAR:   set.intersection_update
    }

    @classmethod
    def comboName( cls, name: str ) -> bool:
        return name.find( cls.OR_CHAR ) != -1

    @classmethod
    def operation_repr(cls, op_char: str, *calendars) -> str:
        assert len(calendars) > 1, 'there must be at least 2 calendars'
        assert op_char in cls.s_ops, f'Unknown op char = {op_char}'

        cal_names = []
        for cal_or_name in calendars:
            if isinstance(cal_or_name, Calendar):
                cname = cal_or_name.name
            elif isinstance(cal_or_name, str):
                #cal = Calendar.instanceById( cal_or_name )
                #assert cal, f"Unknown calendar '{cal_or_name}'"
                #cal = Calendar(name = cal_or_name)

                cname = cal_or_name
            else:
                assert False, f"Invalid calendar/name '{cal_or_name}'"

            cal_names.append(cname)

        return f"{cls.MORE_CHAR.join(sorted(cal_names))}{cls.MORE_CHAR}{op_char}{len(cal_names)}{cls.OP_CHAR}"

    def __init__(self):
        self.stack = deque()
        self.non_working_days = set()

    @classmethod
    def parse(cls, name: str) -> set:
        parser = cls()
        non_working_days = parser.non_working_days
        stack = parser.stack

        operation_repr_list = name.split(cls.OP_CHAR)
        if len(operation_repr_list) == 1:     #-- regular (stored) calendar
            return None

        for operation_repr in operation_repr_list:
            if not operation_repr:
                continue

            name_list_op_num_args = operation_repr.split(cls.MORE_CHAR)
            if len(name_list_op_num_args) > 1:    #-- name list followed by op with num_args
                for cname in name_list_op_num_args[:-1]:
                    if cname:
                        cal = Calendar.instanceById( cname )
                        assert cal, f"Unknown calendar '{cname}"
                        stack.append(cal)

            op_with_num_args = name_list_op_num_args[-1]
            op_char = op_with_num_args[0]
            op = cls.s_ops.get(op_char)
            assert op, f'Unknown op char {op_char}'
            try:
                num_args = int(op_with_num_args[1:])
            except Exception:
                assert False, f'Invalid num_args = {op_with_num_args[1:]}'

            for _ in range( num_args ):
                cal: Calendar = stack.pop()
                assert isinstance(cal, Calendar), f'{cal} must be a Calendar'

                if not non_working_days:
                    non_working_days.update(cal._non_working_days)
                else:
                    op(non_working_days, cal._non_working_days)

            stack.append(Calendar(_non_working_days = non_working_days))

        return non_working_days

#class Calendar(Traitable, _keep_history = True, _force_default_cache = True ):
class Calendar(Traitable, _keep_history = True):
    name: str               = T(T.ID | T.READONLY)
    name_base: str          = T(T.NOT_EMPTY)
    qualifier: str          = T('')
    adjusted_for: str       = T('')
    description: str        = T(T.NOT_EMPTY, ui_hint = Ui('Calendar Description'))
    non_working_days: list  = T(ui_hint = Ui('Non-Working Days'))

    _non_working_days: set  = RT()

    def name_get(self) -> str:
        parts = (self.name_base, self.qualifier, self.adjusted_for)
        return '_'.join(p for p in parts if p)

    @classmethod
    def instance( cls, name: str = None, _create = None, _cache_only = False, **kwargs ) -> 'Calendar':
        assert name, 'name is required'
        if CalendarNameParser.comboName( name ):
            _create = True
            _cache_only = True

        return super().instance( name = name, _create = _create, _cache_only = _cache_only, **kwargs )

    @classmethod
    def AND(cls, *calendars) -> 'Calendar':
        if not calendars:
            return None

        name = CalendarNameParser.operation_repr(CalendarNameParser.AND_CHAR, *calendars)
        return cls(name = name)
    intersection = AND

    @classmethod
    def OR(cls, *calendars) -> 'Calendar':
        if not calendars:
            return None

        name = CalendarNameParser.operation_repr(CalendarNameParser.OR_CHAR, *calendars)
        return cls(name = name)

    @classmethod
    def union(cls, *calendars) -> 'Calendar':
        if len(calendars) > 1:
            return cls.OR(*calendars)
        assert calendars, 'At least one calendar is required for union()'
        return cls(name = calendars[0])

    def non_working_days_get(self) -> list:
        non_working_days = CalendarNameParser.parse(self.name)
        return sorted(non_working_days) if non_working_days else []

    def _non_working_days_get(self) -> set:
        return set(self.non_working_days)

    def add_non_working_days(self, *days_to_add):
        if not days_to_add:
            return

        all_dates = all(type(hd) is date for hd in days_to_add)
        if not all_dates:
            raise TypeError('Every day to add must be a date')

        old_non_working_days = set(self.non_working_days)
        non_working_days = old_non_working_days.union(days_to_add)
        if len(old_non_working_days) == len(non_working_days):
            return

        self.non_working_days = list(non_working_days)

    def replace_non_working_day(self, old_d: date, new_d: date = None):
        """
        if new_d is None, the old_d will be removed
        """
        if old_d == new_d:
            return

        assert new_d is None or type(new_d) is date, f"new_d = '{new_d}' is not a date"
        non_working_days = self.non_working_days

        try:
            i = non_working_days.index(old_d)
            if new_d is not None:
                non_working_days[i] = new_d
            else:
                non_working_days.pop(i)

        except Exception:
            return

        self.non_working_days = non_working_days

    def is_bizday(self, d: date) -> bool:
        return d not in self._non_working_days

    def next_bizday(self, d: date) -> date:
        dt = timedelta(days = 1)
        d += dt
        while not self.is_bizday(d):
            d += dt

        return d

    def prev_bizday(self, d: date) -> date:
        dt = timedelta(days = -1)
        d += dt
        while not self.is_bizday(d):
            d += dt

        return d

    def add_bizdays(self, d: date, biz_days: int) -> date:
        if not biz_days:
            return d

        if biz_days > 0:
            for _ in range(biz_days):
                d = self.next_bizday(d)
        else:
            for _ in range(-biz_days):
                d = self.prev_bizday(d)

        return d

    # def adjustedCalendar( self, replace_days: Iterable, biz_days = True ) -> 'Calendar':
    #     if not replace_days:
    #         return self
    #
    #     start_date = min( replace_days )
    #     end_date = max( replace_days )
    #     num_days = ( end_date - start_date ).days
    #
    #     one_day = timedelta( days = 1 )
    #     d = start_date - one_day
    #     replace_days_range = set( d for _ in range( num_days ) if ( d := d + one_day ) )
    #     if not biz_days:
    #         new_non_working_days = ( self._non_working_days() - replace_days_range ) | set( replace_days )
    #     else:
    #         new_non_working_days = ( self._non_working_days() | replace_days_range ) - set( replace_days )
    #
    #     return self.clone(
    #         name                = f'{self.name()}/{hex( id( replace_days ) )}',
    #         _non_working_days   = new_non_working_days
    #     )

    # def iterateBizDays( self, roll_rule: 'BIZDAY_ROLL_RULE', start_date: date, end_date: date, end_included = False ):
    #     if not self.isBizDay( start_date ):
    #         start_date = roll_rule( self, start_date )
    #     op = le if end_included else lt
    #     yield start_date
    #
    #     dt = self.nextBizDay( start_date )
    #     while op( dt, end_date ):
    #         yield dt
    #         dt = self.nextBizDay( dt )



