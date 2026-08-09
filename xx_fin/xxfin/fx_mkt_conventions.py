from core_10x.traitable import RT, M, T
from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate, date

from xxfin.ccy_cross import Ccy, CcyCross, FinCalendar
from xxfin.ir_rate_mkt_conventions import DAY_COUNT_CONVENTION, IRRateMktConventions, SpotMktConventions


class FXMktConventions(SpotMktConventions):
    'FX (e.g., GBP/USD) Conventions'

    ## Thoughts:
    ## 1. ID traits should be cross and funding_rate_mkt_name, e.g., GBP/USD|SOFR or USD/JPY|SOFR or EUR/GBP|SOFR
    ## 2. maybe should distinguish the case of cross involving the funding ccy (e.g.., dollar crosses for S-funding),
    #     like GBP/USD --> GBP|SOFR or USD/CAD --> CAD|SOFR

    funding_rate_mkt_name: str              = T('SOFR')         // 'SOFR because it is USD-funded default, unless USD rate is customized'

    dc_convention: DAY_COUNT_CONVENTION     = T(DAY_COUNT_CONVENTION.ACT360)    // 'Day Count Convention'
    roll_rule: BIZDAY_ROLL_RULE             = T(BIZDAY_ROLL_RULE.FOLLOWING)
    spot_offset: RDate                      = T(RDate('2B'))
    settle_offset: RDate                    = T(RDate('2B'))

    ccy: Ccy                                = M(T.RUNTIME)
    calendar: FinCalendar                   = M(T.RUNTIME)
    settlement_calendar: FinCalendar        = M(T.RUNTIME)

    cross: CcyCross                         = RT()
    funding_ccy: Ccy                        = RT()
    # disc_mkt_name: str                      = RT()      // 'e.g., JPY_SOFR for USD-funded USD/JPY, or GBP_SOFR, etc.'
    # disc_mkt_conventions: IRRateMktConventions = RT()

    ## return normal_cross
    def cross_get(self) -> CcyCross:
        cross = CcyCross(cross = self.mkt_name)
        bccy = cross.base_ccy.name
        qccy = cross.quote_ccy.name
        fccy = self.funding_ccy.name
        assert fccy in {bccy, qccy}, f'May not have a {fccy}-funded discount curve for the cross {cross}'
        return cross

    def calendar_get(self) -> FinCalendar:  ## calendar of non-USD base or quote and USD
        return self.cross.calendar

    def settlement_calendar_get(self) -> FinCalendar:
        return self.calendar

    def spot_date(self, start_date: date) -> date:
        return self.spot_offset.apply(start_date, self.calendar, self.roll_rule)

    def ccy_get(self) -> Ccy:
        return self.funding_ccy

    def funding_ccy_get(self) -> Ccy:
        funding_mc = IRRateMktConventions.existing_instance(mkt_name = self.funding_rate_mkt_name)
        return funding_mc.ccy

    def non_usd_ccys(self) -> str:
        return '_'.join(set(self.mkt_name.split('/')) - {'USD'})

    def ccys(self) -> str:
        return '_'.join(set(self.mkt_name.split('/')))

    # def disc_mkt_name_get(self) -> str:
    #     """
    #     GBP/USD --> GBP_SOFR
    #     USD/JPY --> JPY_SOFR
    #     """
    #     bccy = self.cross.base_ccy.name
    #     qccy = self.cross.quote_ccy.name
    #     fccy = self.funding_ccy.name
    #     return f'{(qccy if fccy == bccy else bccy)}_{self.funding_rate_mkt_name}'

    # def disc_mkt_conventions_get(self):
    #     return IRRateMktConventions.update(
    #         mkt_name            = self.disc_mkt_name,
    #         ccy                 = self.funding_ccy,
    #         calendar            = self.calendar,
    #         settle_offset       = self.settle_offset,
    #         roll_rule_to_settle = self.roll_rule_to_settle,
    #         settlement_calendar = self.settlement_calendar,
    #         spot_offset         = self.spot_offset,
    #         roll_rule           = self.roll_rule,
    #     )
