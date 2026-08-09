import gc

if __name__ == '__main__':
    #-- CXX related flags must be OFF!
    from xxcommon.xxcommon_env_vars import XXCommonEnvVars

    from xxfin.xxfin_env_vars import XXFinEnvVars

    XXCommonEnvVars.use_cxx_curve = False
    XXFinEnvVars.use_cxxfin = False

    from datetime import date

    from core_10x.exec_control import GRAPH_ON
    from core_10x.logger import PerfTimer

    from xxfin.ccy import Ccy
    from xxfin.ccy_forward import CcyForward
    from xxfin.jit_aadc.aadc_kernel import AadcKernel

    gc.disable()

    ccy      = Ccy('GBP')
    end_date = date(2035, 12, 12)

    def run_scenario(use_graph: bool):
        """
        Builds a fresh CcyForward and an AadcKernel for its price, either off-graph (no
        cross-call caching -- every access recomputes everything from scratch) or on-graph
        (GRAPH_ON active, so the Python baseline is a single genuinely-cached recomputation).
        See aadc_kernel_doc.md's "Measuring acceleration honestly" section for why this choice
        of baseline changes the reported acceleration by ~3 orders of magnitude.
        """
        label = 'ON-GRAPH' if use_graph else 'OFF-GRAPH'
        print(f'\n=== {label} baseline ===')

        cf = CcyForward(denominated = ccy, end_date = end_date)

        with PerfTimer() as t:
            warmup_price = cf.price   #-- loads mkt data / calendars; discard this timing
        print(f'Warmup: {warmup_price:.10f}  ({t.elapsed/1e3:.2f} us)')

        graph = None
        if use_graph:
            graph = GRAPH_ON()
            graph.begin_using()

        with PerfTimer() as t:
            py_price = cf.price
        py_elapsed = t.elapsed
        print(f'Python: {py_price:.10f}  ({py_elapsed/1e3:.2f} us)')

        kernel = AadcKernel(cf.T.price, graph = graph)
        kernel.build()

        kernel.eval()   #-- warm up the AADC call path itself, just in case
        with PerfTimer() as t:
            aadc_price = kernel.eval()
        aadc_elapsed = t.elapsed
        print(f'AADC:   {aadc_price:.10f}  match = {abs(aadc_price - py_price) < 1e-8}  ({aadc_elapsed/1e3:.2f} us)')

        acceleration = py_elapsed / aadc_elapsed
        print(f'AADC acceleration = {acceleration:.1f}')
        return acceleration, kernel

    off_graph_acceleration, _              = run_scenario(use_graph = False)
    on_graph_acceleration,  kernel         = run_scenario(use_graph = True)

    print(f'\n\nSummary: off-graph baseline -> {off_graph_acceleration:.1f}x,  on-graph baseline -> {on_graph_acceleration:.1f}x')

    #-- Using the on-graph kernel (the realistic one) for the rest of the demo:
    print(f'\nAADC Kernel recorded -- {len(kernel.input_handles)} market dependencies discovered')
    for (cls, quotable_id), h in kernel.input_handles.items():
        print(f'  {cls.__name__:<30}  id = {quotable_id}  value = {kernel.inputs[h]:.6f}')

    price, adjoints = kernel.eval_with_adjoints()
    print('\nAdjoints d(price)/d(quote_i):')
    for (cls, quotable_id), adj in adjoints.items():
        print(f'  {cls.__name__:<30}  id = {quotable_id}  dP/dQ = {adj:.6e}')

    #-- Reprice under a bumped quote, without rebuilding the kernel
    some_key = next(iter(kernel.input_handles))
    bumped_value = kernel.inputs[kernel.input_handles[some_key]] + 0.0001
    bumped_price = kernel.eval(market_values = {some_key: bumped_value})
    print(f'\nbumped {some_key[1]} by 1bp -> price = {bumped_price:.10f}  (delta = {bumped_price - price:.6e})')
