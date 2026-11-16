"""Unit tests for core_10x/exec_control.py."""

from __future__ import annotations

import gc
import subprocess
import sys
import textwrap
import weakref

from core_10x import exec_control
from core_10x.exec_control import GRAPH_ON, ExecControl
from core_10x.package_refactoring import PackageRefactoring


class TestExecControl:
    def test_all_caps_names_are_the_class_methods(self):
        names = [name for name, member in vars(ExecControl).items() if isinstance(member, staticmethod)]
        assert names
        for name in names:
            assert getattr(exec_control, name.upper()) is getattr(ExecControl, name)

    def test_class_id_round_trip(self):
        """Why ExecControl is a class: the family can be referenced by one class id."""
        assert PackageRefactoring.find_class(PackageRefactoring.find_class_id(ExecControl)) is ExecControl


def run_script(script: str) -> subprocess.CompletedProcess:
    #-- a separate process: the failures these tests guard against are segfaults
    return subprocess.run([sys.executable, '-c', textwrap.dedent(script)], capture_output=True, text=True, check=False)


class TestProcessorLifetime:
    def test_the_stack_keeps_a_processor_alive_until_end_using(self):
        r = run_script("""
            import gc, weakref
            from core_10x.exec_control import BTP, GRAPH_ON

            proc = GRAPH_ON()
            ref = weakref.ref(proc)
            proc.begin_using()
            del proc
            gc.collect()
            print(ref() is not None)
            BTP.current().end_using()
            gc.collect()
            print(ref() is None)
        """)
        assert r.returncode == 0, r.stderr
        assert r.stdout.split() == ['True', 'True']

    def test_a_with_block_releases_its_processor(self):
        proc = GRAPH_ON()
        ref = weakref.ref(proc)
        with proc:
            pass
        del proc
        gc.collect()
        assert ref() is None

    def test_an_unreferenced_processor_survives_on_the_stack(self):
        r = run_script("""
            import gc
            from core_10x.exec_control import CACHE_ONLY, GRAPH_ON
            from core_10x.traitable import T, Traitable

            with CACHE_ONLY():
                class X(Traitable):
                    name: str = T(T.ID)
                    v: int = T(default=1)

                GRAPH_ON().begin_using()
                gc.collect()
                print(X(name='a').v)
        """)
        assert r.returncode == 0, r.stderr
        assert r.stdout.split() == ['1']

    def test_interleaved_asyncio_scopes_raise_instead_of_crashing(self):
        r = run_script("""
            import asyncio
            from core_10x.exec_control import CACHE_ONLY, GRAPH_ON
            from core_10x.traitable import T, Traitable

            with CACHE_ONLY():
                class X(Traitable):
                    name: str = T(T.ID)
                    v: int = T(default=1)

                async def task(n):
                    with GRAPH_ON():
                        await asyncio.sleep(0.01)
                        return X(name=f't{n}').v

                async def main():
                    return await asyncio.gather(task(1), task(2), return_exceptions=True)

                print([str(e) for e in asyncio.run(main())])
        """)
        assert r.returncode == 0, r.stderr
        assert r.stdout.count('Mismanaged XControl block') == 2
