"""Hand-built AADC recording of ``MonarchButterfly.locomotive_speed``.

Unit-test twin of ``manual_tests/aadc_monarch_butterfly_test.py``, and the deliberate counterexample
to ``test_aadc_raw_ccy_forward.py``: that one records a straight-line pricing path and expects
**zero** passive warnings, this one records a path that branches on an active value and expects
**exactly one**.

The branch is ``locomotive_speed_get``'s metamorphosis guard (``if age_days < ...``). AADC records a
single fixed control flow, so comparing an active value against the threshold converts it to a
passive bool -- one ``IBOOL2BOOL`` warning -- and freezes the caterpillar branch into the tape.
``test_frozen_branch_kills_the_date_adjoint`` pins the consequence: the recording is blind to the
date it branched on, which is exactly why "empty is the goal" for ``passive_warnings()``.
"""

import inspect
from datetime import date

import pytest
from core_10x.code_samples.monarch_butterfly import ExternalWorld, MonarchButterfly
from core_10x.testlib.strict import need

try:
    #-- optional `aadc` extra (private index). Deferred to setup_method's need() so an
    #-- under-provisioned strict CI job fails loudly instead of collect-erroring here.
    from aadc import idouble
    from aadc.evaluate_wrappers import evaluate_kernel

    from xxfin.jit_aadc.aadc_context import AADCContext
    AADC_INSTALLED = True
except ImportError:
    AADC_INSTALLED = False

AADC_REASON = 'aadc not installed (py10x-fin-base[aadc] extra)'

#-- Newborn, so the recording takes the caterpillar branch: speed tracks leaf mass, not wind.
DOB      = date.today()
SPEED_TOL = 1e-12
FD_BUMP   = 1e-6


def _guard_line_range() -> range:
    """Source lines of ``locomotive_speed_get`` -- where the metamorphosis guard must live.

    Beats hard-coding the line number the warning reports, which drifts whenever the sample is
    edited.
    """
    lines, first = inspect.getsourcelines(MonarchButterfly.locomotive_speed_get)
    return range(first, first + len(lines))


class TestAadcMonarchButterfly:
    def setup_method(self):
        need(AADC_INSTALLED, AADC_REASON)

        self.monarch = MonarchButterfly(dob = DOB)
        self.world   = ExternalWorld.current()
        self.py_speed = self.monarch.locomotive_speed

        self.current_date = float(self.world.current_date)
        self.leaf_mass    = float(self.world.leaf_mass_available)

        with AADCContext() as kernel:
            active_date = idouble(self.current_date)
            active_mass = idouble(self.leaf_mass)
            self.world.current_date        = active_date
            self.world.leaf_mass_available = active_mass

            self.date_in = active_date.mark_as_input()
            self.mass_in = active_mass.mark_as_input()

            self.speed_out = self.monarch.locomotive_speed.mark_as_output()

        self.kernel = kernel
        self.world.current_date        = self.current_date   #-- back to plain floats, off-kernel
        self.world.leaf_mass_available = self.leaf_mass

        self.inputs = { self.date_in: self.current_date, self.mass_in: self.leaf_mass }

    def teardown_method(self):
        #-- test_isolation asserts no Traitable outlives the test; drop our references explicitly.
        self.monarch = self.world = None

    def _speed_and_adjoints(self) -> tuple[float, dict]:
        handles = [self.date_in, self.mass_in]
        result  = evaluate_kernel(self.kernel, {self.speed_out: handles}, self.inputs, 1)
        derivs  = result.derivs[self.speed_out]
        return result.values[self.speed_out].item(), { h: derivs[h].item() for h in handles }

    def test_records_exactly_one_passive_warning(self):
        warnings = self.kernel.passive_warnings()
        assert self.kernel.num_passive_warnings() == 1, f'expected only the metamorphosis guard, got {warnings}'

        (warning,) = warnings
        assert warning['kind_name'] == 'IBOOL2BOOL', warning
        assert warning['count'] == 1, warning

    def test_the_warning_points_at_the_metamorphosis_guard(self):
        (warning,) = self.kernel.passive_warnings()
        assert warning['file'] == inspect.getsourcefile(MonarchButterfly)
        assert warning['line'] in _guard_line_range(), \
            f'warning at line {warning["line"]} is outside locomotive_speed_get'

    def test_speed_matches_python(self):
        speed, _ = self._speed_and_adjoints()
        assert speed == pytest.approx(self.py_speed, abs = SPEED_TOL)

    def test_leaf_mass_adjoint_matches_finite_difference(self):
        """The caterpillar branch *is* recorded, so its own sensitivity is exact."""
        _, adjoints = self._speed_and_adjoints()

        self.world.leaf_mass_available = self.leaf_mass + FD_BUMP
        up = self.monarch.locomotive_speed
        self.world.leaf_mass_available = self.leaf_mass - FD_BUMP
        down = self.monarch.locomotive_speed
        self.world.leaf_mass_available = self.leaf_mass

        fd = (up - down) / (2 * FD_BUMP)
        assert adjoints[self.mass_in] == pytest.approx(fd, rel = 1e-6)

    def test_frozen_branch_kills_the_date_adjoint(self):
        """What the passive warning costs: ``current_date`` reached the output only through the
        frozen comparison, so the tape reports no sensitivity to it at all."""
        _, adjoints = self._speed_and_adjoints()
        assert adjoints[self.date_in] == 0.
