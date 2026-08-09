from xxcommon.curve import IP_KIND, CurveParams, DateCurve

from xxfin.fx_forward_curve_mas import FxForwardCurveMas
from xxfin.fx_spot_fwd_quotable import FXForwardQuotable, FXMktConventions, FXSpotQuotable
from xxfin.ir_zero_rate_curve import ZeroRateCurve
from xxfin.rate_curve import AccrualRatioCurve, RateCurve
from xxfin.synthetic_mkt_data import RT, M, SyntheticMktDataWithoutMas, T, TenorBasedSyntheticCurve

_DBG = False

###########################################################################################################
###
### The following is a boneheaded FX forward curve with simple inter-/extrapolation from the quoted rates
### It gives some fx rates, but not as good an interpolation as from the corresponding fx funding fx curve
### (in particular, not consistent with the rate interpolations).
### But it's simple as a door knob, and won't mistaken the pound for the yen rates
###
###########################################################################################################

class FXForwardCurveSimple(TenorBasedSyntheticCurve, mas_class = FxForwardCurveMas):
    mkt_conventions: FXMktConventions   = M()
    payload: DateCurve                  = M(T.EMBEDDED)

    now_rate: float                     = RT()

    def now_rate_get(self) -> float:
        return self.payload.value(self.md_date)

    def quotables_by_class_get(self) -> dict:
        today           = self.md_date
        mc              = self.mkt_conventions
        cal             = mc.calendar
        roll_rule       = mc.roll_rule
        spot_date       = mc.spot_date(today)

        mkt_basis = self.md_basis
        mao = self.mkt_assembly_object

        spot_data_definition = mao.quotable_stubs_by_class.get(FXSpotQuotable)
        if spot_data_definition is None:
            raise AssertionError(f'Spot FX rate quote must be present to build an FX forward curve for {self.mkt_name}')

        quotables = {}
        spot_quotable = FXSpotQuotable.existing_instance(**mkt_basis)
        quotables[FXSpotQuotable] = {spot_date: spot_quotable}

        fwd_data_definition = mao.quotable_stubs_by_class.get(FXForwardQuotable)
        forwards = {}
        quotables[FXForwardQuotable] = forwards
        for stub in mao.create_quotable_stubs(FXForwardQuotable, fwd_data_definition, today):
            tenor = stub['tenor']  ## stub does have tenor; trying to create FXForwardQuotable too early isn't good
            start_date = today if tenor.symbol() == '1B' else spot_date
            d = tenor.apply(start_date, cal, roll_rule)
            if d == spot_date:
                raise AssertionError(f'{self.mkt_name} >>> {tenor.symbol()} <<< forward specification conflicts with spot rate')   ## TODO: may check before raising if the conflicting rate value is diff from the spot rate
            quotable = FXForwardQuotable.existing_instance(**stub, **mkt_basis)
            # tenor = quotable.tenor
            # start_date = today if tenor.symbol() == '1B' else spot_date
            # d = tenor.apply(start_date, cal, roll_rule)
            # if d == spot_date:
            #     raise AssertionError(f'{self.mkt_name} >>> {tenor.symbol()} <<< forward specification conflicts with spot rate')   ## TODO: may check before raising if the conflicting rate value is diff from the spot rate

            forwards[d] = quotable

        return quotables

    def payload_get(self) -> DateCurve:
        fx_crv = DateCurve(beginning_of_time = self.md_date)
        for q_cls, quotables_by_date in self.quotables_by_class.items():
            for d, quotable in quotables_by_date.items():
                fx_crv.update(d, quotable.quote)

        ## if only spot rate is given (no forwards) then use it for all fx conversions
        if len(fx_crv.values) < 2:
            fx_crv.params = CurveParams(ip_kind = IP_KIND.ZERO)

        # fx_crv.flat_extrapolate_params()
        return fx_crv

    #def quotables_prior_to(self, max_date: date) -> dict:
        # mc          = self.mkt_conventions
        # mas_data    = self.mkt_assembly
        # mkt_basis   = self.md_basis
        # cal         = mc.calendar
        # roll_rule   = mc.roll_rule
        # today       = self.md_date
        #
        # spot_quotable = FXSpotQuotable.existing_instance(**mkt_basis)
        # quotables = { FXSpotQuotable: [spot_quotable] }
        #
        # quotable_cls = FXForwardQuotable
        # all_tenors = mas_data.get(quotable_cls)
        # spot_date = self.mkt_conventions.spot_date(today)
        # tenors = RDate.prior_to(all_tenors, spot_date, max_date, cal, roll_rule, overstep = True)
        # quotables[quotable_cls] = [ quotable_cls.existing_instance(tenor = tenor, **mkt_basis) for tenor in tenors ]
        #
        # return quotables

class FXFundedDiscRateCurve(SyntheticMktDataWithoutMas):
    mkt_conventions: FXMktConventions   = M()
    payload: RateCurve                  = M(T.EMBEDDED)

    funding_rate_mkt_name: str          = T(T.ID)

    def payload_get(self) -> RateCurve:
        res = RateCurve(beginning_of_time = self.md_date)  ## no natural rate quoting conventions for the funded discount rate

        ## have this fx fwd fn only bcz later we may have x-ccy swaps
        ## we don't need to pass in mkt_basis and mas_data
        self.process_fx_spot_fwds(res)
        # res.flat_extrapolate_params()

        return res

    def invert(self) -> int:
        mc = self.mkt_conventions
        ## TODO: need ccy.name as the Ccy objects were diffrent !!
        return -1 if mc.cross.quote_ccy.name is mc.funding_ccy.name else 1    ## fx fwd ratio = (FX(d)/FX(0)) for cross = fccy/ccy and FX(0)/FX(d) for ccy/fccy

    def process_fx_spot_fwds(self, ccy_disc_curve: RateCurve):
        """
        LOGIC:
        ccy_disc_curve.update(d, rate_from_accrual(funding_curve.accrual(d) * FX(d)/FX(today)))     ## assuming the cross = fccy/ccy
        """
        provider_name   = self.provider_name
        today           = self.md_date
        snapshot        = self.snapshot

        #-- 1) FX Forward Curve Simple
        fx_fwd_curve_object = FXForwardCurveSimple(
            mkt_name        = self.mkt_conventions.mkt_name,
            provider_name   = provider_name,
            md_date         = today,
            snapshot        = snapshot
        )
        fx_fwd_curve = fx_fwd_curve_object.payload      #-- it will either get it, if already built, or build right here

        #-- 2) Funding Zero Rate Curve
        funding_curve_object = ZeroRateCurve(
            mkt_name        = self.mkt_conventions.funding_rate_mkt_name,
            provider_name   = provider_name,
            md_date         = today,
            snapshot        = snapshot
        )
        funding_curve = funding_curve_object.payload  #-- it will either get it, if already built, or build right here

        if _DBG:    # pragma: no cover
            print( self.mkt_conventions.cross)
            # ccY  = self.mkt_conventions.ccy
            # fccY = self.mkt_conventions.funding_ccy

        if _DBG: print(f'curves dc/compound: ccy_disc - {ccy_disc_curve.compounding}/{ccy_disc_curve.dc_convention}; funding_curve - {funding_curve.compounding}/{funding_curve.dc_convention}\n')  # pragma: no cover

        dates_fx_rates  = fx_fwd_curve.dates_values()   ## the mkt quotes
        fx0             = fx_fwd_curve_object.now_rate
        invert          = self.invert()
        for d, fx in dates_fx_rates:
            ccy_disc_curve.update(d, ccy_disc_curve.internal_rate_from_accrual(d, funding_curve.accrual(d) * (fx/fx0)**invert))

            if _DBG:    # pragma: no cover
                print(f'date = {d}/{d.strftime("%A")}, fwd/now fx = {fx}/{fx0}, fwd fx ratio (for {self.mkt_conventions.cross}) = {(fx/fx0)**invert}, ')
                print(f'$ accrual/ $ rate = {funding_curve.accrual(d)}/{funding_curve.value(d)}, '
                      f'ccy accrual/ ccy rate = {funding_curve.accrual(d)*((fx/fx0)**invert)}/{ccy_disc_curve.rate_from_accrual(d, funding_curve.accrual(d) * ((fx/fx0)**invert))}, ')
                print(f'check: ccy accrual = {ccy_disc_curve.accrual(d)} vs funding-curve fwd_fx_ratio-adj accrual {(fx/fx0)**invert * funding_curve.accrual(d)}; ')
                print(f'check: calc-ed fx rate: {fx0*(ccy_disc_curve.accrual(d)/funding_curve.accrual(d))**invert} vs quoted {fx};\n')


class FXForwardCurve(SyntheticMktDataWithoutMas):
    """
    - build FXFundingDiscCurve
    - calc FXFwd( d ) = ccy_disc_crv.accrual(d)/funding_crv.accrual( d ) * FX(today)    e.g., USD/JPY(d) = JPY_USD.accrual(d)/SOFR.accrual(d) * USD/JPY(0)
    """
    mkt_conventions: FXMktConventions       = M()
    payload: AccrualRatioCurve              = M(T.EMBEDDED)   // 'calc FX(d)  = FX(today) * (accrual of funded ccy curve(d) / accrual of funding curve(d))**invert '

    funding_disc_curve: ZeroRateCurve       = RT()  // 'e.g., SOFR'
    ccy_disc_curve: FXFundedDiscRateCurve   = RT()  // 'e.g., GBP|SOFR'
    now_rate: float                         = RT()  // 'e.g., GBP/USD today'

    def funding_disc_curve_get(self) -> ZeroRateCurve:
        zrc = ZeroRateCurve(
            provider_name   = self.provider_name,
            mkt_name        = self.mkt_conventions.funding_rate_mkt_name,
            md_date         = self.md_date,
            snapshot        = self.snapshot,
        )
        _ = zrc.payload
        return zrc

    def ccy_disc_curve_get(self) -> FXFundedDiscRateCurve:
        res = FXFundedDiscRateCurve(
            provider_name   = self.provider_name,
            md_date         = self.md_date,
            snapshot        = self.snapshot,
            mkt_name        = self.mkt_name,
            funding_rate_mkt_name = self.mkt_conventions.funding_rate_mkt_name
        )
        _ = res.payload
        return res

    def payload_get(self) -> AccrualRatioCurve:
        invert              = self.ccy_disc_curve.invert()
        ccy_disc_curve      = self.ccy_disc_curve.payload
        funding_disc_curve  = self.funding_disc_curve.payload

        ## FX(d) = FX(0) * ccy_accrual / fccy_accrual for fccy/ccy cross (and inverse accrual ratio for inverted cross)
        if invert == -1:
            under_curve = ccy_disc_curve
            over_curve  = funding_disc_curve
        else:
            over_curve  = ccy_disc_curve
            under_curve = funding_disc_curve

        res = AccrualRatioCurve(
            beginning_of_time   = self.md_date,
            over_curve          = over_curve,
            under_curve         = under_curve,
            scale               = self.now_rate
        )

        return res

    def now_rate_get(self) -> float:
        fx_fwd_curve = FXForwardCurveSimple(
            provider_name   = self.provider_name,
            mkt_name        = self.mkt_conventions.mkt_name,
            md_date         = self.md_date,
            snapshot        = self.snapshot,
        )
        return fx_fwd_curve.now_rate