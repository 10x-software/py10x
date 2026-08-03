import core_10x
import py10x_kernel
import pytest


@pytest.mark.parametrize('pattern', ['0.0.0', 'unknown'])
def test_versions(pattern):
    assert pattern not in core_10x.__version__
    assert pattern not in py10x_kernel.__version__
