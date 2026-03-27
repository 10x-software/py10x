if __name__ == '__main__':
    from datetime import datetime

    from core_10x.logger import PerfTimer
    from core_10x.jit.manual_tests.basic_test import Calc
    from core_10x.jit.trait_getter_cython_compiler import CythonCompiler, FuncTreeWalker

    #seed = int(datetime.utcnow().timestamp())
    seed = 123
    calc = Calc(seed = seed)
    calc.count = 10_000

    trait_name = 'abracadabra'

    with PerfTimer() as t:
        p = calc.get_value(trait_name)
    dt = t.elapsed

    #-- compile
    cc = CythonCompiler.instance(Calc, trait_name)
    cc.tcc_compile()
    compiled_getter = cc.compiled_getter
    trait = Calc.trait(trait_name)
    trait.set_f_get(compiled_getter, True)

    #-- benchmark
    with PerfTimer() as t:
        p2 = calc.get_value(trait_name)
    dt_jit = t.elapsed

    print('')
    print(f'data:           {p}, {p2}')
    print(f'acceleration:   {dt / dt_jit:.1f}')

