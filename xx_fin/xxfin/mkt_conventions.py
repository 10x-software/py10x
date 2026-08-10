from __future__ import annotations

from datetime import date

from core_10x.traitable import RC, RT, T, Traitable
from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate

from xxfin.ccy import Ccy
from xxfin.fin_calendar import FinCalendar

#-- TODO: _keep_history = True, _force_default_cache = True
class MktConventions(Traitable):
    """
    Base class for representation of conventions in a given financial market.
    Examples:
        IRRateMktConventions|SOFR: details of how standard contracts (cash deposits, futures/FRATerms, swaps) on SOFR tradable (calendars, day counting, etc.)
        IRBasisSwapMktConventions|SONIA/SOFR: details of how standard basis swaps on SONIA/SOFR trade
        EQMktConventions|AMZN: details of how AMZN trades (exchanges, holidays, settlement delays, currency, etc.)
        FXMktConventions|EUR/USD: details of how EUR/USD trades
    """
    mkt_name: str                           = T(T.ID)
    ccy: Ccy                                = T()
    calendar: FinCalendar                   = T()

    settle_offset: RDate                    = T()
    roll_rule_to_settle: BIZDAY_ROLL_RULE   = T()
    settlement_calendar: FinCalendar        = T()

    def ccy_get(self) -> Ccy:
        return Ccy.USD()

    def settle_offset_get(self) -> RDate:
        return self.ccy.settle_offset

    def roll_rule_to_settle_get(self):
        return self.ccy.roll_rule

    def calendar_get(self) -> FinCalendar:
        return self.ccy.bank_calendar

    def settlement_calendar_get(self) -> FinCalendar:
        return self.calendar

    def settlement_date(self, end_date: date) -> date:
        return self.settle_offset.apply(end_date, self.settlement_calendar, self.roll_rule_to_settle)

    pay_date = settlement_date

    ## WARNING: in general may not recover expiration date from settlement due to roll
    def expiration_date(self, settlement_date: date) -> date:
        go_back = self.settle_offset * (-1)
        return go_back.apply(settlement_date, self.settlement_calendar, self.roll_rule_to_settle)

class SpotMktConventions(MktConventions):
    spot_offset: RDate                      = T()
    fixing_offset: RDate                    = T(RDate('-1B'))   //  '<= 0 number of biz days back to its fixing date'
    roll_rule_for_fixing: BIZDAY_ROLL_RULE  = T(BIZDAY_ROLL_RULE.FOLLOWING)
    roll_rule: BIZDAY_ROLL_RULE             = T()

    ## how can we not need it? how can it be different? maybe we mean something different for OIS ?
    # fixing_offset                           = RDate('-1B'),
    # fixing_frequency                        = RDate('1B')
    # roll_rule_for_fixing                    = BIZDAY_ROLL_RULE.FOLLOWING,

    def spot_offset_get(self) -> RDate:
        return self.ccy.spot_offset

    def roll_rule_get(self):
        return self.ccy.roll_rule

    def spot_date(self, start_date: date) -> date:
        ccy = self.ccy
        return self.spot_offset.apply(start_date, ccy.bank_calendar, ccy.roll_rule)

    def fix_date(self, start_date: date) -> date:
        return self.fixing_offset.apply(start_date, self.calendar, BIZDAY_ROLL_RULE.PRECEDING) ## explicit PRECEDING here is bcz we go back in time for the fixing

