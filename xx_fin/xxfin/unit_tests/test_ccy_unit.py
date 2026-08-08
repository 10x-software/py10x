from xxfin.ccy_forward import Ccy, CcyUnit, PricingContext


class TestCcyUnit:
    def setup_method(self):
        self.usd = CcyUnit.existing_instance(denominated = Ccy('USD'))
        self.gbp = CcyUnit.existing_instance(denominated = Ccy('GBP'))
        self.cad = CcyUnit.existing_instance(denominated = Ccy('CAD'))
        self.cus = [self.usd, self.gbp, self.cad]
        self.pc  = PricingContext.current()

    def test_price(self):
        for cu in self.cus:
            assert cu.price == 1.

    def test_mkt_deps(self):
        for cu in self.cus:
            assert cu.mkt_deps == {}

    def test_mkt_deps_deps_for_discounting(self):
        for cu in self.cus:
            assert cu.mkt_deps_for_discounting == {}

    def test_max_date(self):
        for cu in self.cus:
            assert cu.max_date() == self.pc.current().md_date
