import cxxfin
import py10x_kernel
import pytest
from core_10x.trait_definition import RT
from core_10x.traitable import Traitable


@pytest.mark.parametrize(
    'values, expected',
    [
        ([2, 3, 5], 30),
        ([1, 2, 3, 4, 5], 120),
        ([7], 7),
        ([], 1),
        ([-1, -2, 3], 6),
    ],
)
def test_product(values, expected):
    assert cxxfin.product(values) == expected


class TestCxxSampleTraitable:
    class SampleTraitable(Traitable):
        s_cxx_mixins = [cxxfin.BSampleTraitable]

        trait1: int = RT(10)
        trait2: float = RT(1.5)
        trait3: float = RT()

    def test_trait3_cxx_getter(self):
        t = self.SampleTraitable()
        assert t.get_trait_value(t.trait('trait3')) == 15.0
