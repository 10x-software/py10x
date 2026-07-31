from __future__ import annotations

import pytest
from core_10x.exec_control import GRAPH_ON, GraphDeps
from core_10x.rc import RC
from core_10x.trait_definition import RT, T
from core_10x.traitable import Traitable
from core_10x.traitable_id import ID


# ---------------------------------------------------------------------------
# Shared leaves
# ---------------------------------------------------------------------------

class Leaf(Traitable):
    name: str = RT(T.ID)
    payload: float = RT()


class Shared(Traitable):
    name: str = RT(T.ID)
    n: int = RT()


@pytest.fixture
def gp():
    with GRAPH_ON() as g:
        yield g


def _payload_deps(gp, bound_trait):
    return list(GraphDeps(gp, bound_trait, Leaf, 'payload').deps(trait_names=True))


def _rev_deps(gp, bound_trait, target_cls=Leaf):
    return list(GraphDeps(gp, bound_trait, target_cls, '_rev').deps(trait_names=True))


# ---------------------------------------------------------------------------
# 1) get_value inside custom setters (and converters)
# ---------------------------------------------------------------------------

class BoxWithSetter(Traitable):
    name: str = RT(T.ID)
    x: float = RT()

    def x_set(self, trait, value) -> RC:
        # Plumbing: look at Leaf.payload only to decide/side-effect; not a live dep.
        _ = Leaf(name='L').payload
        return self.raw_set_trait_value(trait, value)


class ParentViaSetter(Traitable):
    name: str = RT(T.ID)
    out: float = RT()
    n_gets = 0

    def out_get(self) -> float:
        type(self).n_gets += 1
        b = BoxWithSetter(name='box')
        b.x = 1.0
        return b.x


class BoxWithConverter(Traitable):
    name: str = RT(T.ID)
    x: int = RT()

    def x_from_str(self, trait, value: str) -> int:
        _ = Leaf(name='L').payload
        return int(value)


class ParentViaConverter(Traitable):
    name: str = RT(T.ID)
    out: int = RT()
    n_gets = 0

    def out_get(self) -> int:
        type(self).n_gets += 1
        b = BoxWithConverter(name='boxc')
        b.x = '7'  # str → int via x_from_str under CONVERT_VALUES
        return b.x


class ParentViaGetter(Traitable):
    """Contrast: the same Leaf.payload read in a *getter* is a real dep."""
    name: str = RT(T.ID)
    out: float = RT()
    n_gets = 0

    def out_get(self) -> float:
        type(self).n_gets += 1
        return Leaf(name='L').payload


class TestCustomSetterAndConverterReads:
    def test_setter_read_not_tracked(self, gp):
        Leaf(name='L').payload = 10.0
        ParentViaSetter.n_gets = 0
        p = ParentViaSetter(name='ps')

        assert p.out == 1.0
        assert _payload_deps(gp, p.T.out) == []

        n0 = ParentViaSetter.n_gets
        Leaf(name='L').payload = 99.0
        assert p.out == 1.0
        assert ParentViaSetter.n_gets == n0  # no invalidation / recompute

    def test_converter_read_not_tracked(self, gp):
        # CONVERT_VALUES so assign-from-str routes through wrapper_f_from_str.
        with GRAPH_ON(convert_values=1) as gp_conv:
            Leaf(name='L').payload = 10.0
            ParentViaConverter.n_gets = 0
            p = ParentViaConverter(name='pc')

            assert p.out == 7
            assert _payload_deps(gp_conv, p.T.out) == []

            n0 = ParentViaConverter.n_gets
            Leaf(name='L').payload = 99.0
            assert p.out == 7
            assert ParentViaConverter.n_gets == n0

    def test_getter_read_is_tracked(self, gp):
        Leaf(name='L').payload = 10.0
        ParentViaGetter.n_gets = 0
        p = ParentViaGetter(name='pg')

        assert p.out == 10.0
        assert len(_payload_deps(gp, p.T.out)) == 1

        n0 = ParentViaGetter.n_gets
        Leaf(name='L').payload = 30.0
        assert p.out == 30.0
        assert ParentViaGetter.n_gets == n0 + 1


# ---------------------------------------------------------------------------
# 2) ID-trait getters during object construction (endogenous_id)
# ---------------------------------------------------------------------------

class Cross(Traitable):
    """Single ID trait with a getter; construct from base/quote so endogenous_id
    must evaluate `cross_get` to build identity."""
    cross: str = RT(T.ID)
    base: str = RT(T.ID_LIKE)
    quote: str = RT(T.ID_LIKE)

    def cross_get(self) -> str:
        # Read of Shared is identity plumbing, not a dep of the constructing caller.
        _ = Shared(name=self.base).n
        return f'{self.base}/{self.quote}'

    def cross_set(self, trait, cross: str) -> RC:
        a, b = cross.split('/')
        self.set_value('base', a)
        self.set_value('quote', b)
        return self.raw_set_trait_value(trait, cross)


class ParentConstructsByIdTraits(Traitable):
    name: str = RT(T.ID)
    out: str = RT()
    n_gets = 0

    def out_get(self) -> str:
        type(self).n_gets += 1
        # Construct without `cross=` so endogenous_id invokes cross_get.
        # Do not re-read `.cross` afterward — that would be a normal on-graph get
        # of a live trait value (and would legitimately transitively see whatever
        # the ID node itself recorded). The cut we care about is the *caller*.
        Cross(base='GBP', quote='USD')
        return 'ok'


class TestIdTraitGettersOnConstruction:
    def test_id_getter_reads_not_tracked_on_caller(self, gp):
        Shared(name='GBP').n = 1
        ParentConstructsByIdTraits.n_gets = 0
        p = ParentConstructsByIdTraits(name='hid')

        assert p.out == 'ok'
        assert list(GraphDeps(gp, p.T.out, Shared, 'n').deps()) == []

        n0 = ParentConstructsByIdTraits.n_gets
        Shared(name='GBP').n = 99
        assert p.out == 'ok'
        assert ParentConstructsByIdTraits.n_gets == n0


# ---------------------------------------------------------------------------
# 3) get_revision is off-graph
# ---------------------------------------------------------------------------

class ParentReadsRevision(Traitable):
    name: str = RT(T.ID)
    out: int = RT()
    n_gets = 0

    def out_get(self) -> int:
        type(self).n_gets += 1
        return int(Leaf(name='R').get_revision())


class TestGetRevisionOffGraph:
    def test_get_revision_not_tracked(self, gp):
        ParentReadsRevision.n_gets = 0
        p = ParentReadsRevision(name='pr')

        assert p.out == 0
        assert _rev_deps(gp, p.T.out) == []

        n0 = ParentReadsRevision.n_gets
        Leaf(name='R').set_revision(5)
        assert p.out == 0
        assert ParentReadsRevision.n_gets == n0


# ---------------------------------------------------------------------------
# 4) Ccy / CcyCross use-case from xx-fin-domain
# ---------------------------------------------------------------------------

class Ccy(Traitable):
    name: str = RT(T.ID)
    is_deliverable: bool = RT(True)


class CcyCross(Traitable):
    cross: str = RT(T.ID)
    base_ccy: Ccy = RT(T.ID_LIKE)
    quote_ccy: Ccy = RT(T.ID_LIKE)

    def cross_set(self, trait, cross: str) -> RC:
        a, b = cross.split('/')
        self.set_value('base_ccy', Ccy(name=a))
        self.set_value('quote_ccy', Ccy(name=b))
        return self.raw_set_trait_value(trait, cross)

    def cross_get(self) -> str:
        return f'{self.base_ccy.name}/{self.quote_ccy.name}'


class FXMktConventions(Traitable):
    """Minimal stand-in for xxfin.fx_mkt_conventions.FXMktConventions.cross_get."""
    mkt_name: str = RT(T.ID)
    cross: str = RT()

    def cross_get(self) -> str:
        c = CcyCross(cross=self.mkt_name)
        return f'{c.base_ccy.name}/{c.quote_ccy.name}'


class StorableCcy(Traitable):
    """Storable currency: share_object may touch revision / lazy-load."""
    name: str = T(T.ID)
    tag: str = T('x')

    s_store: dict = {}

    @classmethod
    def exists_in_store(cls, id: ID) -> bool:
        return id.value in cls.s_store

    @classmethod
    def load_data(cls, id: ID) -> dict | None:
        return cls.s_store.get(id.value)


class StorableCcyCross(Traitable):
    cross: str = RT(T.ID)
    base_ccy: StorableCcy = RT(T.ID_LIKE)
    quote_ccy: StorableCcy = RT(T.ID_LIKE)

    def cross_set(self, trait, cross: str) -> RC:
        a, b = cross.split('/')
        self.set_value('base_ccy', StorableCcy(name=a))
        self.set_value('quote_ccy', StorableCcy(name=b))
        return self.raw_set_trait_value(trait, cross)

    def cross_get(self) -> str:
        return f'{self.base_ccy.name}/{self.quote_ccy.name}'


class StorableFXMkt(Traitable):
    mkt_name: str = RT(T.ID)
    cross: str = RT()

    def cross_get(self) -> str:
        c = StorableCcyCross(cross=self.mkt_name)
        # Force trait loads that exercise lazy-load / revision paths.
        return f'{c.base_ccy.tag}/{c.quote_ccy.tag}'


@pytest.fixture
def storable_ccy_store():
    StorableCcy.s_store = {
        'GBP': {'_id': 'GBP', 'name': 'GBP', 'tag': 'g', '_rev': 1},
        'USD': {'_id': 'USD', 'name': 'USD', 'tag': 'u', '_rev': 1},
        'CHF': {'_id': 'CHF', 'name': 'CHF', 'tag': 'c', '_rev': 1},
    }
    yield StorableCcy.s_store
    StorableCcy.s_store = {}


class TestCcyUseCase:
    def test_runtime_ccy_cross_under_parent_getter(self, gp):
        """FXMktConventions.cross_get constructs CcyCross (and Ccys) under GRAPH_ON."""
        fx = FXMktConventions(mkt_name='GBP/USD')
        assert fx.cross == 'GBP/USD'
        assert fx.cross == 'GBP/USD'  # stable re-read

        names = {obj.name for _, obj, _, _ in GraphDeps(gp, fx.T.cross, Ccy, 'name').deps()}
        assert names == {'GBP', 'USD'}
        # Construction plumbing must not wire the parent to `_rev`.
        assert _rev_deps(gp, fx.T.cross, Ccy) == []

    def test_storable_ccy_lazy_load_no_wdr(self, gp, storable_ccy_store):
        """Original WDR: share_object/get_revision + later set_revision mid-get.

        Must complete without ``set/invalidate during get`` and without a live
        `_rev` edge from the parent getter.
        """
        fx = StorableFXMkt(mkt_name='GBP/USD')
        assert fx.cross == 'g/u'
        assert _rev_deps(gp, fx.T.cross, StorableCcy) == []

    def test_storable_nested_construct_stable(self, gp, storable_ccy_store):
        fx = StorableFXMkt(mkt_name='CHF/USD')
        assert fx.cross == 'c/u'
        assert fx.cross == 'c/u'
