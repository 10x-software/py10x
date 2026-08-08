from datetime import date

from core_10x.traitable import RT, T, Traitable

from xxfin.ccy_cross import CcyCross
from xxfin.fx_forward_curve import FXForwardCurve
from xxfin.pricing_context import SNAPSHOT, PricingContext


class FxRate(Traitable):
    cross_name: str = RT(T.ID)

    @classmethod
    def quoted_cross_rate(cls, cross: CcyCross, d: date, provider: str, md_date: date, snapshot: SNAPSHOT) -> float:
        fxc_object = FXForwardCurve(
            provider_name = provider,
            md_date = md_date,
            snapshot = snapshot,
            mkt_name = cross.cross
        )
        if d == md_date:
            value = fxc_object.now_rate
        else:
            fxc = fxc_object.payload
            value = fxc.value(d)

        return value

    def rate(self, d: date) -> float:
        # TODO: try quoted rate and if doesnt work then imply from dollar rates
        type1, cross1, type2, cross2 = CcyCross.resolve(cross = self.cross_name)
        if cross1 is None:
            return 1.

        pc = PricingContext.current()
        today = pc.md_date
        provider = pc.mkt_data_provider_name
        snapshot = pc.snapshot

        rate1 = self.quoted_cross_rate(cross1, d, provider, today, snapshot)
        rate2 = self.quoted_cross_rate(cross2, d, provider, today, snapshot) if cross2 else 1.

        return rate1**type1.value * rate2**type2.value


