from core_10x.trait_definition import RT, T
from core_10x.trait_method_error import TraitMethodError
from core_10x.traitable import Traitable

from xxfin.ccy import Ccy
from xxfin.ccy_forward import CcyUnit


class SubCcyUnit(CcyUnit): ...


class EndogenousCcyUnit(SubCcyUnit):
    denominated: Ccy = RT()


class CcyUnitHolder(Traitable):
    ccy_unit: CcyUnit = T()

if __name__=='__main__':
    from xxfin.manual_tests.ccy_unit_test import CcyUnitHolder, EndogenousCcyUnit, SubCcyUnit

    u = CcyUnit.existing_instance(denominated=Ccy.existing_instance(name='GBP'))
    u_ser = u.serialize(False)
    print(u_ser)
    assert u_ser == {'_id': [{'_id': 'GBP'}]} # id is a list of objects, not strings!


    assert CcyUnitHolder(ccy_unit=u).serialize_object()['ccy_unit'] ==  u_ser

    u1 = SubCcyUnit.existing_instance(denominated=Ccy.existing_instance(name='GBP'))
    assert CcyUnitHolder(ccy_unit=u1).serialize_object()['ccy_unit'] ==  {'_type': '_nx', '_cls': 'xxfin/manual_tests/ccy_unit_test/SubCcyUnit', '_obj': u_ser}

    h1 = CcyUnitHolder(ccy_unit=EndogenousCcyUnit(denominated=Ccy(name='GBP')))
    try:
        h1.serialize_object()
    except TraitMethodError as e:
        print(e) # as expected!
    else:
        assert False, "Expected Exception"