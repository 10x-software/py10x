
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

    #inputs_spec = {ExternalWorld: ('current_date', 'leaf_mass_available',)}    #-- fires due to missing wind_speed
    inputs_spec = {ExternalWorld: ('current_date', 'leaf_mass_available', 'wind_speed')}
    exec = AadcExec(mb.T.locomotive_speed, inputs_spec)
    with exec:
        kernel, py_res = exec.create_kernel()
        is_valid, res = exec.eval_kernel(kernel)
        assert is_valid and py_res == res

        w.current_date = w.current_date + timedelta(days = 10)  #-- past metamorphosis -- must flip the branch

        is_valid, res = exec.eval_kernel(kernel)
        print(f'after inputs change, same kernel: is_valid={is_valid} (expect False -- branch flipped)')

        kernel2, py_res2 = exec.create_kernel()  #-- rebuild for the new (butterfly) branch signature
        is_valid, res2 = exec.eval_kernel(kernel2)
        print(f'after rebuild: is_valid={is_valid}, res={res2}, py_res={py_res2}')
