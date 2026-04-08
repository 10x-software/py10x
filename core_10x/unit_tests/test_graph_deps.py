from __future__ import annotations

import pytest
from core_10x.exec_control import GRAPH_OFF, GRAPH_ON, GraphDeps
from core_10x.trait_definition import RT, T
from core_10x.traitable import Traitable


class TestGraphDeps:
    class Quote(Traitable):
        symbol: str   = RT(T.ID)
        price:  float = RT()

    class Portfolio(Traitable):
        name:      str   = RT(T.ID)
        q1_symbol: str   = RT()
        q2_symbol: str   = RT()
        value:     float = RT()

        def value_get(self) -> float:
            # TestGraphDeps is resolved at call time from the module globals.
            quote_cls = TestGraphDeps.Quote
            return quote_cls(symbol=self.q1_symbol).price + quote_cls(symbol=self.q2_symbol).price

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    @pytest.fixture
    def gp(self):
        """GRAPH_ON processor, active for the duration of each test."""
        with GRAPH_ON() as g:
            yield g

    @pytest.fixture
    def portfolio(self, gp):
        """Portfolio primed with AAPL=100 and MSFT=200.

        Returns pf only — q1/q2 are discoverable via GraphDeps.deps().
        pf.value is intentionally NOT pre-computed; each test primes
        the graph itself.
        """
        q1 = TestGraphDeps.Quote(symbol='AAPL')
        q2 = TestGraphDeps.Quote(symbol='MSFT')
        q1.price = 100.0
        q2.price = 200.0
        pf = TestGraphDeps.Portfolio(name='tech')
        pf.q1_symbol = 'AAPL'
        pf.q2_symbol = 'MSFT'
        return pf

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_discovers_dependencies(self, gp, portfolio):
        """GraphDeps finds exactly the two Quote nodes that feed portfolio.value."""
        pf = portfolio
        assert pf.value == 300.0  # prime the graph

        gd = GraphDeps(gp, pf.T.value, self.Quote, 'price')
        results = list(gd.deps())

        assert len(results) == 2
        price_trait = self.Quote.T.price.trait
        for cls, obj, trait, value in results:
            assert cls is self.Quote
            assert isinstance(obj, self.Quote)
            assert trait is price_trait
            assert isinstance(value, float)

        by_symbol = {obj.symbol: value for _, obj, _, value in results}
        assert by_symbol == {'AAPL': 100.0, 'MSFT': 200.0}

    def test_empty_without_graph(self, portfolio):
        """A GRAPH_OFF processor has no node cache — deps() is always empty."""
        pf = portfolio
        with GRAPH_OFF() as gp_off:
            gd = GraphDeps(gp_off, pf.T.value, self.Quote, 'price')
            assert list(gd.deps()) == []

    def test_deps_trait_names_flag(self, gp, portfolio):
        """deps(trait_names=True) yields string names; all other elements still valid."""
        pf = portfolio
        assert pf.value == 300.0

        gd = GraphDeps(gp, pf.T.value, self.Quote, 'price')
        results = list(gd.deps(trait_names=True))

        assert len(results) == 2
        for cls, obj, trait_name, value in results:
            assert cls is self.Quote
            assert isinstance(obj, self.Quote)
            assert trait_name == 'price'
            assert isinstance(value, float)

    def test_deps_ids_flag(self, gp, portfolio):
        """deps(objects=False) yields raw IDs; all other elements still valid."""
        pf = portfolio
        assert pf.value == 300.0

        gd = GraphDeps(gp, pf.T.value, self.Quote, 'price')
        price_trait = self.Quote.T.price.trait
        results = list(gd.deps(objects=False))

        assert len(results) == 2
        for cls, obj_id, trait, value in results:
            assert cls is self.Quote
            assert not isinstance(obj_id, self.Quote)
            assert trait is price_trait
            assert isinstance(value, float)

    def test_wrong_target_class(self, gp, portfolio):
        """No results when target_class has no successor nodes under portfolio.value."""
        pf = portfolio
        assert pf.value == 300.0

        gd = GraphDeps(gp, pf.T.value, self.Portfolio, 'value')
        assert list(gd.deps()) == []

    def test_wrong_trait_name(self, gp, portfolio):
        """No results when the trait name does not exist on the target class."""
        pf = portfolio
        assert pf.value == 300.0

        gd = GraphDeps(gp, pf.T.value, self.Quote, 'nonexistent_trait')
        assert list(gd.deps()) == []

    def test_zero_trait_names(self, gp, portfolio):
        """No trait names → C++ short-circuits immediately, returning empty."""
        pf = portfolio
        assert pf.value == 300.0

        gd = GraphDeps(gp, pf.T.value, self.Quote)
        assert list(gd.deps()) == []

    def test_perturb(self, gp, portfolio):
        """perturb() overwrites a cached node; trait and id come from deps() itself."""
        pf = portfolio
        assert pf.value == 300.0

        gd = GraphDeps(gp, pf.T.value, self.Quote, 'price')
        for cls, obj, trait, val in gd.deps():
            assert cls is self.Quote
            assert isinstance(obj, self.Quote)
            assert trait is self.Quote.T.price.trait
            assert isinstance(val, float)
            if obj.symbol == 'AAPL':
                gd.perturb(cls, obj.id(), trait, 150.0)

        assert self.Quote(symbol='AAPL').price == 150.0

    def test_perturb_value(self, gp, portfolio):
        """perturb_value() convenience wrapper; obj comes from deps()."""
        pf = portfolio
        assert pf.value == 300.0

        gd = GraphDeps(gp, pf.T.value, self.Quote, 'price')
        for cls, obj, trait, val in gd.deps():
            assert cls is self.Quote
            assert isinstance(obj, self.Quote)
            assert trait is self.Quote.T.price.trait
            assert isinstance(val, float)
            if obj.symbol == 'MSFT':
                gd.perturb_value(obj, 'price', 250.0)

        assert self.Quote(symbol='MSFT').price == 250.0

    def test_reflects_price_update(self, gp, portfolio):
        """After a normal price change, GraphDeps reports the updated cached value."""
        pf = portfolio
        assert pf.value == 300.0

        self.Quote(symbol='AAPL').price = 110.0
        assert pf.value == 310.0  # graph re-evaluated

        gd = GraphDeps(gp, pf.T.value, self.Quote, 'price')
        price_trait = self.Quote.T.price.trait
        results = list(gd.deps())

        assert len(results) == 2
        for cls, obj, trait, value in results:
            assert cls is self.Quote
            assert isinstance(obj, self.Quote)
            assert trait is price_trait
            assert isinstance(value, float)

        by_symbol = {obj.symbol: value for _, obj, _, value in results}
        assert by_symbol == {'AAPL': 110.0, 'MSFT': 200.0}
