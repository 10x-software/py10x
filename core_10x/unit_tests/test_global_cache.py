from core_10x.global_cache import cache


# ----------------------------------------------------------------------------
#   keep_value=True (normal caching behavior)
# ----------------------------------------------------------------------------

def test_cache_default_no_args():
    calls = []
    @cache
    def f():
        calls.append(1)
        return 42
    assert f() == 42
    assert f() == 42
    assert len(calls) == 1


def test_cache_default_single_arg():
    calls = []
    @cache
    def f(x):
        calls.append(x)
        return x * 2
    assert f(3) == 6
    assert f(3) == 6
    assert calls == [3]
    assert f(4) == 8
    assert calls == [3, 4]


# ----------------------------------------------------------------------------
#   keep_value=False (side-effect only: run at most once, return real value
#   on first call, None on subsequent hits)
# ----------------------------------------------------------------------------

def test_cache_keep_value_false_no_args():
    """Test @cache(keep_value=False) for 0-argument functions (side-effect only).

    First call executes and returns the real value.
    Subsequent calls must not re-execute and must return None.
    """
    calls = []

    @cache(keep_value=False)
    def side_effect_only():
        calls.append(1)
        return "expensive_result"

    # First invocation: runs, returns real value
    result1 = side_effect_only()
    assert result1 == "expensive_result"
    assert len(calls) == 1

    # Subsequent: no re-run, returns None
    result2 = side_effect_only()
    assert result2 is None
    assert len(calls) == 1

    result3 = side_effect_only()
    assert result3 is None
    assert len(calls) == 1

    # After clear(), it should execute again
    side_effect_only.clear()
    result4 = side_effect_only()
    assert result4 == "expensive_result"
    assert len(calls) == 2


def test_cache_keep_value_false_single_arg():
    calls = []
    @cache(keep_value=False)
    def f(x):
        calls.append(x)
        return x * 2

    assert f(5) == 10
    assert f(5) is None
    assert calls == [5]

    assert f(6) == 12
    assert f(6) is None
    assert calls == [5, 6]


def test_cache_keep_value_false_classmethod():
    """Common usage pattern: classmethods with side effects only."""
    calls = []

    class Demo:
        @classmethod
        @cache(keep_value=False)
        def compute(cls, x):
            calls.append((cls, x))
            return x + 100

    assert Demo.compute(1) == 101
    assert Demo.compute(1) is None
    assert len(calls) == 1

    assert Demo.compute(2) == 102
    assert len(calls) == 2


def test_cache_keep_value_false_multi_arg():
    calls = []
    @cache(keep_value=False)
    def f(a, b, *, c=0):
        calls.append((a, b, c))
        return a + b + c

    assert f(1, 2, c=3) == 6
    assert f(1, 2, c=3) is None
    assert calls == [(1, 2, 3)]

    assert f(4, 5) == 9
    assert len(calls) == 2


def test_cache_keep_value_false_clear():
    calls = []
    @cache(keep_value=False)
    def f(x):
        calls.append(x)
        return x * 10

    assert f(7) == 70
    assert f(7) is None
    assert calls == [7]

    f.clear()
    assert f(7) == 70
    assert calls == [7, 7]
