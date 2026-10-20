if __name__ == '__main__':
    from xxcommon.jit_aadc.aadc_exec import AadcExec, AadcKernel
    AadcExec.instrumentation_registry(
        target_base_classes = (
            'core_10x.code_samples.monarch_butterfly.MonarchButterfly',
        ),
    )

    from datetime import date, timedelta

    from core_10x.code_samples.monarch_butterfly import MonarchButterfly, ExternalWorld


    num_days_back = 7

    today = date.today()
    dob = today - timedelta(days = num_days_back)

    w = ExternalWorld.current()
    mb = MonarchButterfly(name = 'John', dob = dob)

    inputs_spec = {ExternalWorld: ('current_date', 'leaf_mass_available', 'wind_speed')}
    exec = AadcExec(mb.T.locomotive_speed, inputs_spec)
    with exec:
        def result():
            k = exec.current_kernel
            return k._unwrap(k.eval_result.values[k.output])

        exec.new_kernel()
        kernel = exec.current_kernel
        exec.eval_current_kernel()
        assert mb.locomotive_speed == result()

        w.current_date = w.current_date + timedelta(days = 10)  #-- past metamorphosis -- must flip the branch

        is_valid = exec.eval_current_kernel()
        print(f'after inputs change, same kernel: is_valid={is_valid} (expect False -- branch flipped)')

        exec.new_kernel()  #-- rebuild for the new (butterfly) branch signature
        is_valid = exec.eval_current_kernel()
        print(f'after rebuild: is_valid={is_valid}, res={result()}, py_res={mb.locomotive_speed}')

        w.current_date = today  #-- back to the original (caterpillar) state -- same signature as the first kernel

        exec.new_kernel()
        print(f'after moving inputs back: same kernel as original build: {exec.current_kernel is kernel}')
        is_valid = exec.eval_current_kernel()
        print(f'is_valid={is_valid}, res={result()}, py_res={mb.locomotive_speed}')
        assert exec.current_kernel is kernel and is_valid and mb.locomotive_speed == result()
