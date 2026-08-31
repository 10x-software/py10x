import QuantLib as ql

from xxfin.ir_cash_deposit_quotable import IRCashDepositQuotable
from xxfin.ir_swap_quotable import IRSwapQuotable
from xxfin.ir_zero_rate_curve import ZeroRateCurve
from xxfin.ql_adapter import QL
from xxfin.rate_curve import RateCurve


class ZeroRateCurveQL(ZeroRateCurve):
    """
    Alternative ZeroRateCurve.payload_get() using QuantLib's own PiecewiseLinearZero bootstrap
    instead of the native root-solver in py_zrc_bootstrap.py. PiecewiseLinearZero specifically
    (not e.g. PiecewiseLogLinearDiscount) is required for the result to be numerically
    comparable to the native curve, since linear interpolation is invariant to the day-count
    rescaling of its time axis (verified empirically).

    Swaps are OIS (fixed vs. compounded-overnight, single curve for both forecasting and
    discounting -- confirmed by RateCurve.swap_rate_simple_compounding()'s telescoping-annuity
    formula), calibrated via ql.OISRateHelper against ql.OvernightIndex whose forecast curve
    is a RelinkableYieldTermStructureHandle linked back to the curve being built here.
    """
    def payload_get(self) -> RateCurve:
        today = self.md_date
        mc = self.mkt_conventions
        ql_today = QL.to_date(today)
        ql.Settings.instance().evaluationDate = ql_today

        deposit_quotables = self.quotables_by_class.get(IRCashDepositQuotable, {})
        helpers = [QL.deposit_helper(q, mc) for q in deposit_quotables.values()]

        swap_quotables = self.quotables_by_class.get(IRSwapQuotable, {})
        forecast_curve = None
        if swap_quotables:
            forecast_curve = ql.RelinkableYieldTermStructureHandle()
            index = QL.overnight_index(mc, forecast_curve)
            helpers += [QL.swap_helper(q, mc, index) for q in swap_quotables.values()]

        res = RateCurve(beginning_of_time = today, quoting_dc_convention = mc.dc_convention, quoting_compounding = mc.compounding)

        #-- RateCurve's own internal storage convention (dc_convention/compounding), read directly
        #   off the object being built rather than duplicated as a separate constant
        day_counter = QL.day_counter(res.dc_convention)
        compounding, frequency = QL.compounding(res.compounding)

        ql_curve = ql.PiecewiseLinearZero(ql_today, helpers, day_counter)
        if forecast_curve is not None:
            #-- self-referential: the OIS helpers forecast off the very curve being bootstrapped
            #   here, via the handle they were built against -- must link before the first query
            #   below triggers the (lazy) bootstrap solve
            forecast_curve.linkTo(ql_curve)
        ql_curve.enableExtrapolation()

        for d in ql_curve.dates():
            zero_rate = ql_curve.zeroRate(d, day_counter, compounding, frequency).rate()
            res.update(d.to_date(), zero_rate)

        res.set_curve_params_to_flat_extrapolate()
        return res
