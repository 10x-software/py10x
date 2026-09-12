"""
Basic EdgeDepsTracker check against the MonarchButterfly narrative example (core_10x/code_samples/monarch_butterfly.py):
the same source-line `if` in `locomotive_speed_get` must fire once per evaluation, and its recorded outcome must
flip once the individual crosses the metamorphosis threshold -- exactly the branch flip AADC needs to detect
instead of silently trusting a stale recording.

Run directly: python -m core_10x.manual_tests.edge_deps_tracker_basic_test
"""

import core_10x.traitable  # noqa: F401 -- force the framework's own module to finish loading first
# EdgeDepsTracker.instrument_class() runs from Traitable.__init_subclass__, so flipping use_edge_deps_tracker before
# core_10x.traitable itself has finished loading would instrument core_10x's own internal Traitable subclasses too.

from datetime import date, timedelta

from core_10x.environment_variables import EnvVars

#-- instrument_class() only fires from Traitable.__init_subclass__ at class-definition time, so this must happen
#   BEFORE MonarchButterfly is imported below. edge_dep_tracker_class_name defaults to '', which resolves to the
#   base EdgeDepsTracker facility -- no AADC involved.
EnvVars.use_edge_deps_tracker = True

from core_10x.code_samples.monarch_butterfly import EXTERNAL_WORLD_NAME, ExternalWorld, MonarchButterfly

EnvVars.use_edge_deps_tracker = False  #-- restore right away -- don't instrument anything else

from core_10x.edge_deps_tracker import EdgeDepsTracker
from core_10x.exec_control import CACHE_ONLY

if __name__ == '__main__':
    with CACHE_ONLY():
        today = date.today()

        #-- app code's job, not MonarchButterfly's: provision the shared external-world instance
        ExternalWorld(name = EXTERNAL_WORLD_NAME, leaf_mass_available = 50., wind_speed = 5., _update = True)

        caterpillar = MonarchButterfly(name = 'specimen-young', dob = today - timedelta(days = 5), _update = True)
        butterfly = MonarchButterfly(name = 'specimen-old', dob = today - timedelta(days = 20), _update = True)

        with EdgeDepsTracker() as tracker:
            print(f'caterpillar speed = {caterpillar.locomotive_speed:.3f} cm/s')
            print(f'butterfly speed   = {butterfly.locomotive_speed:.3f} cm/s')
            path = tracker.execution_path()

        print(f'execution_path = {path}')

        #-- one guard occurrence per evaluation: the caterpillar took one branch, the butterfly the other -- same
        #   source-line guard, opposite outcomes.
        assert len(path) == 2
        outcomes = {outcome for _, outcome in path}
        assert outcomes == {True, False}, 'expected the two evaluations to take opposite branches'

        print('OK: EdgeDepsTracker recorded both outcomes of the same guard -- the branch flip that a one-shot priming pass would otherwise miss')
