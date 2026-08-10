from __future__ import annotations

from datetime import date

from core_10x.global_cache import cache
from core_10x.traitable import RT, NamedTraitable, T, Traitable
from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate

from xxfin.fin_calendar import FinCalendar

#-- TODO: _force_default_cache = True
class Ccy(NamedTraitable):
    bank_calendar: FinCalendar  = T(T.NOT_EMPTY)
    roll_rule: BIZDAY_ROLL_RULE = T(BIZDAY_ROLL_RULE.FOLLOWING)

    spot_offset: RDate          = T(RDate('2B'))
    settle_offset: RDate        = T(RDate('2B'))

    is_deliverable: bool        = T(True)
    discounting_mkt_name: str   = T(T.NOT_EMPTY)

    is_usd: bool                = RT()

    @staticmethod
    @cache
    def USD() -> Ccy:
        return Ccy('USD')

    def is_usd_get(self) -> bool:
        return self.name == 'USD'

    def pay_date(self, end_date: date) -> date:
        'Payment settlement date corresponding to a given end date'
        return self.settle_offset.apply(end_date, self.bank_calendar, self.roll_rule)

    def spot_date(self, start_date: date) -> date:
        'Spot settlement date corresponding to a given start date'
        return self.spot_offset.apply(start_date, self.bank_calendar, self.roll_rule)

    def expiration_date(self, pay_date: date) -> date:
        'Expiration date corresponding to a given payment settlement date. CAUTION: may not recover the expitation date due to roll'
        go_back = self.settle_offset * (-1)
        return go_back.apply(pay_date, self.bank_calendar, self.roll_rule)

    @classmethod
    def verified(cls, ccy) -> Ccy:
        if type(ccy) is str:
            ccy = Ccy(ccy)

        elif not isinstance(ccy, Ccy):
            raise TypeError(f'Invalid ccy type: {type(ccy)}')

        if not cls.exists_in_store(ccy.id()):
            raise ValueError(f'{ccy} does not exist')

        return ccy

