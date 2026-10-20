"""Regression coverage for AadcExec's stateful kernel API (build/eval/staleness-detect/rebuild/
retrieve) against the monarch butterfly example -- a Traitable whose getter branches on an active
input (metamorphosis), the "edge dependency" case if-wrapping exists for. See
xxcommon/jit_aadc/manual_tests/monarch_butterfly_test.py for the narrative version of this same
scenario and xxcommon/jit_aadc/aadc_exec_summary.md for the design."""

from __future__ import annotations

import importlib.util
from datetime import date, timedelta

import pytest
from core_10x.code_samples.monarch_butterfly import ExternalWorld, MonarchButterfly
from core_10x.exec_control import CACHE_ONLY
from core_10x.testlib.strict import need
from core_10x.traitable import RT, T, Traitable

need(importlib.util.find_spec('aadc') is not None, 'aadc not installed (py10x-core[aadc] extra)')

from xxcommon.jit_aadc.aadc_exec import AadcExec  # noqa: E402

AadcExec.instrumentation_registry(
    target_base_classes = ('core_10x.code_samples.monarch_butterfly.MonarchButterfly',),
)


class UnregisteredLarva(Traitable):
    """Same date branch as MonarchButterfly.locomotive_speed_get, but outside the registered bases."""
    dob: date               = T(T.ID)
    locomotive_speed: float = RT()

    def locomotive_speed_get(self) -> float:
        ew = ExternalWorld.current()
        if (ew.current_date - self.dob).days < 14:
            return ew.leaf_mass_available
        return ew.wind_speed


def test_aadc_exec_kernel_reuse_and_staleness_detection():
    today = date.today()
    dob = today - timedelta(days = 7)   #-- still a caterpillar (< s_age_at_metamorphosis_days)

    with CACHE_ONLY():
        w = ExternalWorld.current()
        mb = MonarchButterfly(name = 'John', dob = dob)

        inputs_spec = {ExternalWorld: ('current_date', 'leaf_mass_available', 'wind_speed')}
        with AadcExec(mb.T.locomotive_speed, inputs_spec) as exec_:
            exec_.new_kernel()
            caterpillar_kernel = exec_.current_kernel
            assert exec_.eval_current_kernel()
            assert exec_.result() == mb.locomotive_speed

            #-- past metamorphosis -- flips locomotive_speed_get()'s if branch
            w.current_date = w.current_date + timedelta(days = 10)
            assert not exec_.eval_current_kernel(), 'stale kernel must be detected, not silently reused'

            exec_.new_kernel()   #-- rebuilds for the new (butterfly) branch signature
            assert exec_.current_kernel is not caterpillar_kernel
            assert exec_.eval_current_kernel()
            assert exec_.result() == mb.locomotive_speed

            #-- back to the original (caterpillar) state -- same signature as the first kernel
            w.current_date = today
            exec_.new_kernel()
            assert exec_.current_kernel is caterpillar_kernel, 'a previously-seen signature must reuse its kernel'
            assert exec_.eval_current_kernel()
            assert exec_.result() == mb.locomotive_speed


def test_aadc_exec_unregistered_branch_raises():
    #-- an unguarded `if` on an active input would freeze one control flow into the tape -- refuse to build it
    with CACHE_ONLY():
        larva = UnregisteredLarva(dob = date.today() - timedelta(days = 7))
        inputs_spec = {ExternalWorld: ('current_date', 'leaf_mass_available', 'wind_speed')}
        with AadcExec(larva.T.locomotive_speed, inputs_spec) as exec_:
            with pytest.raises(RuntimeError, match = r'IBOOL2BOOL.*UnregisteredLarva\.locomotive_speed_get'):
                exec_.new_kernel()
            assert exec_.current_kernel is None
