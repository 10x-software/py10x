if __name__ == '__main__':
    #-- CXX related flags must be OFF!
    from xxcommon.xxcommon_env_vars import XXCommonEnvVars

    from xxfin.xxfin_env_vars import XXFinEnvVars

    XXCommonEnvVars.use_cxx_curve = False
    XXFinEnvVars.use_cxxfin = False

    #-- no target_base_classes/known_modules -- this pricing path has no edge (branch) dependencies
    #  on active market quotes, so class-level if-wrapping isn't needed; AADCDomainSwap alone covers
    #  correctness (math.*/builtins/curve/root-solver, scoped to the recording pass).
    from xxcommon.jit_aadc.aadc_exec import AadcExec

    from datetime import date

    from core_10x.logger import PerfTimer

    from xxfin.ccy import Ccy
    from xxfin.ccy_forward import CcyForward
    from xxfin.mkt_quotable import SingleMktQuote

    ccy      = Ccy('GBP')
    end_date = date(2035, 12, 12)
    inputs_spec = {SingleMktQuote: ('quote',)}

    cf = CcyForward(denominated = ccy, end_date = end_date)

    with PerfTimer() as t:
        warmup_price = cf.price   #-- loads mkt data / calendars; discard this timing
    print(f'Warmup: {warmup_price:.10f}  ({t.elapsed/1e3:.2f} us)')

    exec_ = AadcExec(cf.T.price, inputs_spec)
    exec_.__enter__()   #-- actually activates instrumentation (apply()), not just builds it

    with PerfTimer() as t:
        py_price = cf.price
    py_elapsed = t.elapsed
    print(f'Python: {py_price:.10f}  ({py_elapsed/1e3:.2f} us)')

    exec_.new_kernel()
    exec_.eval_current_kernel()   #-- warm up the AADC call path itself, just in case
    with PerfTimer() as t:
        exec_.eval_current_kernel()
    aadc_elapsed = t.elapsed
    aadc_price = exec_.result()
    print(f'AADC:   {aadc_price:.10f}  match = {abs(aadc_price - py_price) < 1e-8}  ({aadc_elapsed/1e3:.2f} us)')

    acceleration = py_elapsed / aadc_elapsed
    print(f'AADC acceleration = {acceleration:.1f}')

    kernel = exec_.current_kernel
    print(f'\nAADC Kernel recorded -- {len(kernel.input_handles)} market dependencies discovered')
    for (cls, quotable_id, trait), h in kernel.input_handles.items():
        print(f'  {cls.__name__:<30}  id = {quotable_id}  trait = {trait.name}')

    exec_.eval_current_kernel(with_derivs = True)
    aadc_price = exec_.result()
    print('\nAdjoints d(price)/d(quote_i):')
    for (cls, quotable_id, trait), adj in exec_.derivs().items():
        print(f'  {cls.__name__:<30}  id = {quotable_id}  dP/dQ = {adj:.6e}')

    #-- Reprice under a bumped quote, without rebuilding the kernel -- no more market_values
    #  override dict; bump the live Traitable object directly, same node the kernel reads from.
    (some_cls, some_id, some_trait) = next(iter(kernel.input_handles))
    quote_obj = some_cls(_id = some_id)
    original_value = getattr(quote_obj, some_trait.name)
    setattr(quote_obj, some_trait.name, original_value + 0.0001)

    exec_.eval_current_kernel()
    bumped_price = exec_.result()
    print(f'\nbumped {some_id} by 1bp -> price = {bumped_price:.10f}  (delta = {bumped_price - aadc_price:.6e})')

    exec_.__exit__(None, None, None)
