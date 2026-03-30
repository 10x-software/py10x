
from core_10x.logger import PerfTimer
from core_10x.jit.manual_tests.basic_test import Calc
from core_10x.jit.traitable_optimizer import TraitableOptimizer

def eval_optimizer(test_obj, trait_name: str, mt, verbose = True):
    traitable_class = test_obj.__class__
    TraitableOptimizer.reset(traitable_class, trait_name)
    with PerfTimer() as t:
        value = test_obj.get_value(trait_name)
    dt = t.elapsed

    op_class, op_method = TraitableOptimizer.optimize(traitable_class = traitable_class, attr_name = trait_name, mt = mt)

    if op_class.is_lazy():
        val = test_obj.get_value(trait_name)

    with PerfTimer() as t:
        val = test_obj.get_value(trait_name)
    dt_jit = t.elapsed

    same_values = (value == val)
    if verbose:
        print(f'Optimizer = {mt.__name__}')
        print(f'  data:           {same_values}, {dt/1e6} ms, {dt_jit/1e6} ms')
        print(f'  acceleration:   {dt / dt_jit:.1f}')

    return (same_values, dt, dt_jit)

if __name__ == '__main__':
    from datetime import datetime

    #seed = int(datetime.utcnow().timestamp())
    seed = 123
    calc = Calc(seed = seed)
    calc.count = 100_000

    #trait_name = 'abracadabra'
    trait_name = 'price'

    #same_values, dt, dt_jit = eval_optimizer(calc, trait_name, TraitableOptimizer.CYTHON_TCC)
    #same_values, dt, dt_jit = eval_optimizer(calc, trait_name, TraitableOptimizer.NUMBA)

    op_class, op_method = TraitableOptimizer.optimize(test_obj = calc, attr_name = trait_name)




