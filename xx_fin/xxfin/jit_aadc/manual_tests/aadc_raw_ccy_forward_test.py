import gc

if __name__ == '__main__':
    import py10x_infra
    import py10x_kernel
    print('kernel',py10x_kernel.__file__,py10x_kernel.__version__)
    print('infra',py10x_infra.__file__,py10x_infra.__version__)

    #-- CXX related flags be OFF!
    from xxcommon.xxcommon_env_vars import XXCommonEnvVars

    from xxfin.xxfin_env_vars import XXFinEnvVars

    XXCommonEnvVars.use_cxx_curve = False
    XXFinEnvVars.use_cxxfin = False

    import aadc

    aadc_license = XXFinEnvVars.aadc_license
    if aadc_license:
        aadc.license(aadc_license)     #-- temp license key from Matlogica

    from datetime import date

    from aadc import idouble
    from aadc.evaluate_wrappers import evaluate_kernel
    from core_10x.exec_control import GRAPH_ON
    from core_10x.logger import PerfTimer

    from xxfin.ccy import Ccy
    from xxfin.ccy_forward import CcyForward
    from xxfin.jit_aadc.aadc_context import AADCContext

    end_date = date(2035, 12, 12)
    ccy      = Ccy('GBP')
    cf       = CcyForward(denominated = ccy, end_date = end_date)

    graph_on = GRAPH_ON()
    graph_on.begin_using()

    gc.disable()

    #-- Python baseline
    with PerfTimer() as t:
        py_price = cf.price
    py_elapsed = t.elapsed
    print(f'Warmup: {py_price:.10f}  ({py_elapsed/1e3:.2f} us)')

    #-- Collect quotables feeding the discount curve
    zrc = cf.disc_curve
    all_quotables = {}   #-- quotable -> float_quote
    for cls, qdict in zrc.quotables_by_class.items():
        for d, q in qdict.items():
            all_quotables[q] = float(q.quote)

    for q, fq in all_quotables.items():
        q.quote          = fq

    #-- Python baseline
    with PerfTimer() as t:
        py_price = cf.price
    py_elapsed = t.elapsed
    print(f'Python: {py_price:.10f}  ({py_elapsed/1e3:.2f} us)')


    print(f'\nDiscount curve: {len(all_quotables)} quotables')
    for q, fq in all_quotables.items():
        print(f'  {type(q).__name__:<30}  tenor = {q.tenor}  quote = {fq:.6f}')

    #-- AADC recording
    with AADCContext() as kernel:
        input_handles = {}
        for q, fq in all_quotables.items():
            iq               = idouble(fq)
            q.quote          = iq
            input_handles[q] = iq.mark_as_input()

        price_active = cf.price
        price_out = price_active.mark_as_output()

    print('\nAADC Kernel recorded')

    #-- restore plain float quotes
    for q, fq in all_quotables.items():
        q.quote = fq

    #-- Evaluate Kernel
    inputs = { h: all_quotables[q] for q, h in input_handles.items() }
    deps   = { price_out: list(input_handles.values()) }
    evaluate_kernel(kernel, deps, inputs, 1)   #-- warm up, just in case :-)

    with PerfTimer() as t:
        result = evaluate_kernel(kernel, deps, inputs, 1)
    aadc_elapsed = t.elapsed
    aadc_price = result.values[price_out].item()
    print(f'AADC:   {aadc_price:.10f}  match = {abs(aadc_price - py_price) < 1e-8}  ({aadc_elapsed/1e3:.2f} us)')

    #-- Adjoints: d(price)/d(each_quote)
    print('\nAdjoints d(price)/d(quote_i):')
    for q, h in input_handles.items():
        adj = result.derivs[price_out][h].item()
        print(f'  {type(q).__name__:<30}  tenor = {q.tenor}  dP/dQ = {adj:.6e}')

    print(f'\n\nAADC acceleration = {py_elapsed / aadc_elapsed:.1f}')