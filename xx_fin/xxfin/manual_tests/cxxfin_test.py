import cxxfin
import py10x_kernel
from core_10x.trait_definition import RT
from core_10x.traitable import Traitable

print(f"cxxfin: {cxxfin.__version__} (from {cxxfin.__file__})")

cases = [
    ([2, 3, 5],         30),
    ([1, 2, 3, 4, 5],   120),
    ([7],               7),
    ([],                1),
    ([-1, -2, 3],       6),
]

for values, expected in cases:
    result = cxxfin.product(values)
    status = "OK" if result == expected else f"FAIL (expected {expected})"
    print(f"  product({values}) = {result}  {status}")


class SampleTraitable(Traitable):
    s_cxx_mixins = [cxxfin.BSampleTraitable]

    trait1: int = RT(10)
    trait2: float = RT(1.5)
    trait3: float = RT()

t = SampleTraitable()

for trait in t.traits():
    print( f'value for trait {trait.name}:')
    print(t.get_trait_value(trait))

