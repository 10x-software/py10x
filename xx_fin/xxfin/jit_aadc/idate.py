"""``IDate`` -- a calendar date that can be marked as an AADC input.

AADC's tape is numeric, so a date reaches it as a float ordinal. Wrapping that conversion here
keeps it out of the domain model: a trait stays declared as ``date`` and only the AADC path
swaps an ``IDate`` in, instead of every model that wants to be recordable having to carry its
dates as ordinals.

``IDate`` exposes only as much of ``date`` as the recorded code actually uses -- ordering,
differencing, and shifting by a ``timedelta``. Differencing yields ``IDays``, whose ``.days`` is
a tape value, so ``(d2 - d1).days`` reads the same as it does for real dates.

Branching on an ``IDate`` still raises IBOOL2BOOL, exactly as it would on a bare ``idouble``:
the tape records one fixed control flow, and a date that reaches an ``if`` freezes it. That is
deliberate -- see ``unit_tests/test_aadc_monarch_butterfly.py``, which pins the warning.
"""

from __future__ import annotations

from datetime import date, timedelta

from aadc import idouble


class IDays:
    """An ``IDate`` difference. ``timedelta``'s surface, but ``.days`` may be a tape value."""

    def __init__(self, days):
        self.days = days

    def __repr__(self) -> str:
        return f'IDays({self.days!r})'


class IDate:
    #-- No __eq__/__ne__ on purpose. The ordering operators return ibool, which is what makes a
    #   guard's IBOOL2BOOL visible -- but equality is also what callers (traits comparing an old
    #   value against a new one, dict/set membership) reach for implicitly. An ibool-returning
    #   __eq__ would make those coerce, charging unrelated code a passive warning and costing
    #   hashability. Identity equality inherited from object is the safe default here.

    @staticmethod
    def input_value(value) -> float:
        """The number to feed ``evaluate_kernel`` for a date input. The tape takes floats, so the
        conversion has to happen somewhere -- doing it here keeps callers from open-coding
        ``float(d.toordinal())`` at every replay site. Accepts a ``date`` or an ``IDate``."""
        return float(value.toordinal())

    def __init__(self, value):
        #-- A bare ordinal (an idouble already on the tape) is how __sub__/__add__ build their
        #   result without a second constructor; anything else is date-like. `idouble` has to be
        #   named here -- it is not a float subclass (its mro is just (idouble, object)).
        ordinal = value if isinstance(value, (idouble, int, float)) else value.toordinal()
        self.ordinal = ordinal if isinstance(ordinal, idouble) else idouble(float(ordinal))

    def mark_as_input(self, differentiable = True):
        """``differentiable = False`` records a replay-varying input carrying no adjoint, which
        is what a date is. The default stays differentiable so a caller can still ask for the
        (structurally zero) derivative -- the butterfly test asserts exactly that."""
        return self.ordinal.mark_as_input() if differentiable else self.ordinal.mark_as_input_no_diff()

    def toordinal(self):
        return self.ordinal

    def val(self) -> date:
        """Back to a real ``date``, using the ordinal's current (record-time) value."""
        return date.fromordinal(int(float(self.ordinal)))

    def __sub__(self, other):
        if isinstance(other, timedelta):
            return IDate(self.ordinal - other.days)
        return IDays(self.ordinal - other.toordinal())

    def __rsub__(self, other):
        return IDays(other.toordinal() - self.ordinal)

    def __add__(self, other: timedelta) -> IDate:
        return IDate(self.ordinal + other.days)

    __radd__ = __add__

    def __lt__(self, other):
        return self.ordinal < other.toordinal()

    def __le__(self, other):
        return self.ordinal <= other.toordinal()

    def __gt__(self, other):
        return self.ordinal > other.toordinal()

    def __ge__(self, other):
        return self.ordinal >= other.toordinal()

    def __repr__(self) -> str:
        return f'IDate({self.ordinal!r})'
