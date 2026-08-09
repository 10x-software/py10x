from core_10x.named_constant import NamedConstant
from cxxfin import BCompounding, BCompoundTransform
from cxxfin import compounding_apply as _cxx_compounding_apply


class COMPOUNDING(NamedConstant, BCompounding, symbols_from=BCompounding):
    pass

class COMPOUND_TRANSFORM(NamedConstant, BCompoundTransform, symbols_from=BCompoundTransform):
    pass

def compounding_apply(comp: COMPOUNDING, transform: COMPOUND_TRANSFORM, t: float, v: float) -> float:
    return _cxx_compounding_apply(getattr(BCompounding, comp.name), getattr(BCompoundTransform, transform.name), t, v)
