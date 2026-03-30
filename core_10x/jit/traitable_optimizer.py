from __future__ import annotations

from typing import Callable

from core_10x.traitable import Traitable, Trait, T, RT, XNone
from core_10x.logger import PerfTimer
from core_10x.xinf import XInf
from core_10x.exec_control import GRAPH_OFF

from core_10x.jit.traitable_method_optimizer import TraitableMethodOptimizer, TraitableMethodData, MethodOptimizationRecord
from core_10x.jit.trait_getter_cython_compiler import CythonCompiler
from core_10x.jit.trait_getter_numba_compiler import NumbaCompiler


class TraitableOptimizer:
    GENERAL_PY  = None
    CYTHON_TCC  = CythonCompiler
    NUMBA       = NumbaCompiler
    AADT        = None
    _BEST       = XNone
    s_opt_classes = {CYTHON_TCC, NUMBA,}

    @classmethod
    def optimize(cls,
        traitable_class: type[Traitable]    = None,
        attr_name: str                      = None,
        mt: type[TraitableMethodOptimizer]  = XNone,
        test_obj: Traitable                 = None,
        verbose                             = True,
    ) -> tuple[type[TraitableMethodOptimizer], Callable]:
        assert attr_name, 'attr_name must be a valid name of either a traitor a method'

        if traitable_class:
            assert mt, 'traitable_class is given -> mt must be given as well'
        else:
            assert test_obj and isinstance(test_obj, Traitable), 'test_obj must be an instance of Traitable'
            traitable_class = test_obj.__class__

        if mt is None:
            return (None, None)

        if mt is XNone:
            op_class, op_method = cls.find_best_optimizer(test_obj, attr_name, verbose = verbose)
            return (op_class, op_method) if op_class else (None, None)

        op_obj = mt(traitable_class, attr_name)
        op_obj.optimize()

        return cls.use_optimizer(traitable_class, attr_name, mt)

    @classmethod
    def use_optimizer(
        cls,
        traitable_class: type[Traitable],
        attr_name: str,
        mt: type[TraitableMethodOptimizer],
    ) -> tuple[type[TraitableMethodOptimizer], Callable]:
        data: TraitableMethodData = TraitableMethodData.record(traitable_class, attr_name)
        op_rec: MethodOptimizationRecord = TraitableMethodOptimizer.optimization_record(traitable_class, attr_name)
        op_method = op_rec.get_optimization(mt) if mt else op_rec.original_method
        if not op_method:
            return (None, None)

        trait = data.trait
        if trait:
            trait.set_f_get(op_method, True)
        else:
            setattr(traitable_class, attr_name, op_method)

        return (mt, op_method)

    @classmethod
    def find_best_optimizer(
        cls,
        test_obj: Traitable,            #-- Traitable object for evaluation(s)
        attr_name: str,                 #-- trait name or method name
        num_runs: int   = 5,            #-- number of runs to determine the benchmark
        use_it          = True,         #-- apply the best optimizer, if found
        force           = False,        #-- ignore if already found earlier
        verbose         = True          #-- print some info while going
    ) -> tuple[type[TraitableMethodOptimizer], Callable]:   #-- (op_class, optimized_method)
        traitable_class = test_obj.__class__
        data = TraitableMethodData.record(traitable_class, attr_name)
        op_rec: MethodOptimizationRecord = MethodOptimizationRecord.instance(data.original_method)
        if not force:
            best = op_rec.get_best_optimization()
            if best[0]:
                return best

        results = {}
        op_obj: TraitableMethodOptimizer
        for mt in cls.s_opt_classes:
            mt_name = mt.__name__
            if verbose:
                print(f'Trying to optimize using {mt_name}')
            try:
                op_class, op_method = cls.optimize(traitable_class = traitable_class,  attr_name = attr_name, mt = mt)
                if verbose:
                    print(f'  optimized by {mt_name}.')
            except Exception as ex:
                if verbose:
                    print(f'{mt_name} failed to optimize:\n')
                    print(str(ex))
                continue

            if op_class and op_method:
                results[op_class] = res = [0., 0.]

                if verbose:
                    print(f'  collecting performance data for {mt_name}')
                r = test_obj.get_value(attr_name)
                res[0] = r
                with GRAPH_OFF():
                    with PerfTimer() as clock:
                        for i in range(num_runs):
                            test_obj.get_value(attr_name)

                dt = clock.elapsed
                res[1] = dt

        if verbose:
            print('Determining the best optimizer...')

        cls.reset(traitable_class, attr_name)
        with GRAPH_OFF():
            with PerfTimer() as clock:
                value = test_obj.get_value(attr_name)
        dt = clock.elapsed * num_runs

        min_dt = XInf
        chosen_class = None
        for op_class, (val, elapsed) in results.items():
            if val != value:
                raise ValueError(f'{op_class}: {val} != {value}')

            if verbose:
                print(f'  {op_class.__name__}: {elapsed/1e6} ms  (acc = {dt/elapsed: .1f})')

            if elapsed < min_dt:
                min_dt = elapsed
                chosen_class = op_class

        if not chosen_class:
            return (None, None)

        op_rec.set_best(chosen_class)
        op_method = op_rec.get_optimization(chosen_class)

        if verbose:
            print(f'The best optimizer is {chosen_class.__name__}')

        if use_it:
            return cls.use_optimizer(traitable_class, attr_name, chosen_class)

        return (chosen_class, op_method)

    @classmethod
    def reset(cls, traitable_class: type[Traitable], attr_name: str):
        cls.use_optimizer(traitable_class, attr_name, None)
