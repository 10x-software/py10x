from datetime import date

from core_10x.traitable import T, Traitable

from xxfin.ccy import Ccy
from xxfin.ccy_forward import CcyForward, CcyUnit


class CheckCcyUnitForward(Traitable):
    name: str       = T(T.ID)
    unit: CcyUnit   = T()
    fwd: CcyForward = T()

    def unit_get(self) -> CcyUnit:
        return CcyUnit(denominated = Ccy(name = self.name))

    @classmethod
    def save_retrieve(cls, ccy: Ccy, d: date, save: bool) -> float:
        if save:
            cc = cls(name = ccy.name)
            cc.fwd = CcyForward(denominated=ccy, end_date = d)
            cc.save()
            return -1.
        else:
            cc = CheckCcyUnitForward.existing_instance(name = ccy.name)
            return cc.fwd.price

if __name__ == '__main__':
    from core_10x.exec_control import GRAPH_ON

    from xxfin.manual_tests.ccy_forward_test import CheckCcyUnitForward
    from xxfin.pricing_context import PricingContext

    ccy = Ccy.USD()
    ccy2 = Ccy.existing_instance(name = 'GBP')

    cu = CcyUnit(denominated=ccy)
    price = cu.price

    p1 = cu.price_ccy('GBP')
    p2 = cu.price_ccy('EUR')

    cu2 = CcyUnit(denominated=ccy2)
    price2 = cu2.price

    p21 = cu2.price_ccy('GBP')
    p22 = cu2.price_ccy('EUR')

    print(f'price of {cu} in its denominated {ccy} = {price}, in GBP = {p1}, in EUR = {p2}')
    print(f'price of {cu2} in its denominated {ccy2} = {price2}, in GBP = {p21}, in EUR = {p22}')


    graph_on = GRAPH_ON()
    graph_on.begin_using()

    d0 = PricingContext.current().md_date
    dates = (d0, date(2025, 12, 12), date(2035, 12, 12), date(2125, 12, 12))
    for d in dates:
        cf = CcyForward(denominated=ccy2, end_date = d)
        cfp = cf.price
        cfp2 = cf.price_ccy('EUR')
        print(f'{d}: {cf} price in {cf.denominated} = {cfp}, price in EUR = {cfp2}')


    CheckCcyUnitForward.save_retrieve(ccy2, dates[2], True)
    print(CheckCcyUnitForward.save_retrieve(ccy2, dates[1], False))
