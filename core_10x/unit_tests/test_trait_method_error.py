import traceback

import pytest

from core_10x.rc import RC
from core_10x.trait_definition import T
from core_10x.trait_method_error import TraitMethodError
from core_10x.traitable import Traitable, AnonymousTraitable


OUTPUTS = ['exception', 'object', 'args', 'value']
GROUPS = [
    {'serialize_nx': lambda x: x.serialize_object(False)},
    {'z_deserialize': lambda x: x.__class__.deserialize({'z': 2000}), 'y_get': lambda x: x.y},
    {'x_get': lambda x: x.x(0)},
    {'x_set': lambda x: x.set_value('x', 100, 10)},
]

bombing_methods = {'_'.join(OUTPUTS[: i + 1]): group for i, group in enumerate(GROUPS)}


@pytest.mark.parametrize(argnames=['cnt', 'key'], argvalues=enumerate(bombing_methods.keys()))
def test_trait_method_error(cnt, key):
    class X(AnonymousTraitable):
        x: int
        y: int
        z: int = T(1000)
        t: Traitable = T()

        @classmethod
        def bombing_method(cls, x):
            raise KeyError(x + 1)

        def x_get(self, x):
            return self.bombing_method(x)

        def y_get(self):
            return self.bombing_method(0)

        def x_set(self, trait, value, x) -> RC:
            return self.bombing_method(value)

        @classmethod
        def y_serialize(cls, value):
            return cls.bombing_method(value)

        @classmethod
        def y_deserialize(cls, trait, value):
            return cls.bombing_method(value)

    x = X()
    x.t = X()
    for m, f in bombing_methods[key].items():
        try:
            f(x)
        except TraitMethodError as e:
            e_str = str(e)
            if cnt:
                assert 'KeyError' in e_str
            else:
                assert 'TypeError' in e_str
                assert f'value = {x.t}' in e_str
                assert (
                    "original exception = TypeError: test_trait_method_error.<locals>.X - anonymous' instance may not be serialized as external reference"
                    in e_str
                )

            for i, output in enumerate(key.split('_')):
                expected = i < cnt + 1
                if cnt or (not expected and output != 'value'):
                    assert (f' {output} =' in e_str) is expected, f'did{" not" if expected else ""} find {output} for {key} in {e_str}'
                if cnt:
                    assert f"Failed in <class 'test_trait_method_error.test_trait_method_error.<locals>.X'>.{m.split('_')[0]}.{m}" in e_str

            tb_str = traceback.format_exc()
            if cnt:
                assert 'f(x)' in tb_str
                assert f"'{m}': lambda x: x." in tb_str
                assert 'bombing_method(' in tb_str
                assert 'raise KeyError(x + 1)' in tb_str
