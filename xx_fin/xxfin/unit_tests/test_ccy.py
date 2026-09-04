from datetime import date

import pytest
from xxfin.ccy_cross import Ccy, CcyCross


class TestCcy:
    def setup_method(self):
        # -- Ccy instances must be fresh per test, not shared via setup_class: dev_10x's autouse
        # test_isolation fixture clears XCache after every test, so objects built once for the
        # whole class go stale (origin cache no longer reachable) after the first test runs.
        self.usd = Ccy('USD')
        self.gbp = Ccy('GBP')
        self.cad = Ccy('CAD')
        self.ccys = [self.gbp, self.usd, self.cad]

        self.dd          = [ date(2026, 1, 1), date(2026, 7, 30)]
        self.ed_non_cad  = [ date(2026, 1, 5), date(2026, 8, 3)]
        self.ed_cad      = [ date(2026, 1, 5), date(2026, 8, 4)]


    def test_USD(self):
        assert Ccy.USD() == self.usd

    def test_is_usd(self):
        assert self.usd.is_usd is True
        assert self.gbp.is_usd is False

    def test_pay_date(self):
        for ccy in [self.gbp, self.usd]:
            for ed, pd in zip(self.dd, self.ed_non_cad, strict=True):
                assert ccy.pay_date(ed) == pd
        for ed, pd in zip(self.dd, self.ed_cad, strict=True):
            assert self.cad.pay_date(ed) == pd

    def test_spot_date(self):
        for ccy in [self.gbp, self.usd]:
            for ed, pd in zip(self.dd, self.ed_non_cad, strict=True):
                assert ccy.spot_date(ed) == pd
        for ed, pd in zip(self.dd, self.ed_cad, strict=True):
            assert self.cad.spot_date(ed) == pd

    def test_expiration_date_bad(self):
        d1  = date(2026, 1, 1)
        pd1  = self.usd.pay_date(d1)
        ed1  = self.usd.expiration_date(pd1)
        assert d1 != ed1

    def test_expiration_date_good(self):
        d2  = date(2026, 7, 30)
        pd2  = self.usd.pay_date(d2)
        ed2  = self.usd.expiration_date(pd2)
        assert d2 == ed2

    def test_verified_good(self):
        for ccy in self.ccys:
            assert Ccy.verified(ccy) == ccy

    def test_verified_bad(self):
        for ccy in ['AED', 'XXX']:
            with pytest.raises(ValueError):
                Ccy.verified(ccy)
        for ccy in [3.1415, self.ccys, CcyCross(cross = 'EUR/GBP')]:
            with pytest.raises(TypeError):
                Ccy.verified(ccy)

        strX = 'XXXXX'
        ccyX = Ccy(name=strX, _replace = True)
        assert Ccy.verified(strX) == Ccy(name=strX, _replace=True)
        with pytest.raises(ValueError, match="XXXXX does not exist in Store: <infra_10x.duckdb_store.DuckDbStore object at"):
            assert Ccy.verified(ccyX)