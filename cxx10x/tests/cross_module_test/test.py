import ctypes

import py10x_kernel

import cross_module_test as t

from core_10x.traitable import Traitable
from core_10x.trait_definition import RT


def test_with_s_cxx_mixins():
    class Sample(Traitable):
        s_cxx_mixins = [t.BCrossTestMixin]

        # The "test" trait will use test_get from the C++ mixin.
        test: str = RT()

    s = Sample()
    result = s.test

    assert isinstance(result, str)
    assert result == f"cross_ok:{s.id_value()}"
    print("test_with_s_cxx_mixins: OK")


def test_free_function():
    """Direct free function that accepts BTraitable* in its pybind11 signature."""
    class Sample(Traitable):
        trait1: int = RT(123)

    obj = Sample()

    result = t.free_accept(obj)
    assert isinstance(result, str)
    assert result.startswith("free:"), f"Unexpected result: {result}"
    print("test_free_function: OK ->", result)


def test_null_handling():
    """The C++ side should gracefully handle a null pointer (or Python None)."""
    result = t.free_accept(None)
    assert result == "null"
    print("test_null_handling: OK")


if __name__ == "__main__":
    test_with_s_cxx_mixins()
    test_free_function()
    test_null_handling()
    print("\nAll cross-module tests PASSED")
