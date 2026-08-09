from datetime import date

from core_10x.scenario import Scenario
from xxfin.ccy import Ccy
from xxfin.fin_instrument import FinInstrument
from xxfin.ir_zero_rate_curve import ZeroRateCurve
from xxfin.pricing_context import PricingContext
from xxfin.rate_curve import RateCurve


def kill_discounting(ccy: Ccy):
    pc = PricingContext.current()
    zrc = ZeroRateCurve(
        md_date         = pc.md_date,
        provider_name   = pc.mkt_data_provider_name,
        snapshot        = pc.snapshot,
        mkt_name        = ccy.discounting_mkt_name,
    )
    dc = zrc.payload
    # dc_copy = RateCurve(dates = dc.dates, values = dc.values, begining_of_time = pc.md_date)
    # dc_copy.update_many(dc.times, (0,) * len(dc.times), reset = True)
    # zrc.payload = dc_copy
    dc.update_many(dc.times, (0,) * len(dc.times), reset = True)
    zrc.payload = dc

def discount_curve_mult_shift(ccy: Ccy, multiplier: float) -> dict:
    pc = PricingContext.current()
    zrc = ZeroRateCurve(
        md_date         = pc.md_date,
        provider_name   = pc.mkt_data_provider_name,
        snapshot        = pc.snapshot,
        mkt_name        = ccy.discounting_mkt_name,
    )
    dc = zrc.payload
    print(f'zrc before shift: {dc.dates_values()}')
    new_values = tuple(r * multiplier for r in dc.values)
    dc.update_many(dc.times, new_values, reset = True)
    zrc.payload = dc
    print(f'zrc after shift: {dc.dates_values()}')



if __name__ == '__main__':
    ccy = Ccy.USD()

    d = date(2030, 1, 1)
    df0 = FinInstrument(denominated = ccy).discount_factor(d)

    with Scenario():
        kill_discounting(ccy)
        df1 = FinInstrument(denominated = ccy).discount_factor(d)

    ##zrc.invalidate_value('payload')

    print(f'{ccy.name} discount factor for {d} actual / zero rate: {df0} / {df1}')


