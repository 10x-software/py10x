from xxfin.fx_forward_curve_mas import FxForwardCurveMas
from xxfin.ir_zero_rate_curve_mas import IRZeroRateCurveMas


def run():
    IRZeroRateCurveMas.save_scopes()
    FxForwardCurveMas.save_scopes()

if __name__ == '__main__':
    run()

    # x = IRZeroRateCurveMas.existing_instance(mkt_name = 'SOFR')
    # for (cls, stub) in x.quotable_class_and_stubs_generator():
    #     print(f'{cls}: {stub}')