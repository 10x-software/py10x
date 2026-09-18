import gc
from datetime import date
import py10x_infra
import py10x_kernel

if __name__ == '__main__':
    print('kernel',py10x_kernel.__file__,py10x_kernel.__version__)
    print('infra',py10x_infra.__file__,py10x_infra.__version__)

    from aadc import idouble
    from aadc.evaluate_wrappers import evaluate_kernel
    from core_10x.exec_control import GRAPH_ON
    from core_10x.logger import PerfTimer
    from core_10x.code_samples.monarch_butterfly import MonarchButterfly, ExternalWorld

    from xxfin.jit_aadc.aadc_context import AADCContext
    from xxfin.jit_aadc.idate import IDate

    mb = MonarchButterfly(name = 'bfly', dob = date.today())

    graph_on = GRAPH_ON()
    graph_on.begin_using()

    gc.disable()

    #-- Python warmup
    with PerfTimer() as t:
        py_ls = mb.locomotive_speed
    py_elapsed = t.elapsed
    print(f'Warmup: {py_ls:.10f}  ({py_elapsed/1e3:.2f} us)')

    w = ExternalWorld.current()

    #-- Python baseline
    with PerfTimer() as t:
        py_ls = mb.locomotive_speed
    py_elapsed = t.elapsed
    print(f'Python: {py_ls:.10f}  ({py_elapsed/1e3:.2f} us)')


    print(f'\nDate: {w.current_date}')
    #-- AADC recording
    with AADCContext() as kernel:
        input_handles = {}
        idt                     = IDate(w.current_date)
        w.current_date          = idt
        input_handles['date']   = idt.mark_as_input()

        wst               = idouble(w.leaf_mass_available)
        w.leaf_mass_available = wst
        input_handles['mass'] = wst.mark_as_input()

        ls_active = mb.locomotive_speed
        ls_out = ls_active.mark_as_output()

    print(f'\nAADC Kernel recorded ({kernel.num_passive_warnings()} warnings)')

    #-- restore plain
    w.current_date        = idt.val()
    w.leaf_mass_available = w.leaf_mass_available.val()

    #-- Evaluate Kernel
    inputs = { input_handles['date']: IDate.input_value(w.current_date), input_handles['mass']: w.leaf_mass_available }
    deps   = { ls_out: list(input_handles.values()) }
    evaluate_kernel(kernel, deps, inputs, 1)   #-- warm up, just in case :-)

    with PerfTimer() as t:
        result = evaluate_kernel(kernel, deps, inputs, 1)
    aadc_elapsed = t.elapsed
    aadc_ls = result.values[ls_out].item()
    print(f'AADC:   {aadc_ls:.10f}  match = {abs(aadc_ls - py_ls) < 1e-8}  ({aadc_elapsed/1e3:.2f} us)')

    #-- Adjoints: d(price)/d(each_quote)
    print('\nAdjoints d(price)/d(quote_i):')
    for q, h in input_handles.items():
        adj = result.derivs[ls_out][h].item()
        print(f'  dv/d{q.title()} = {adj:.6e}')

    print(f'\n\nAADC acceleration = {py_elapsed / aadc_elapsed:.1f}')