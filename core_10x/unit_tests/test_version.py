import py10x_core
import pytest

import core_10x


@pytest.mark.parametrize('pattern', ['0.0.0', 'unknown'])
def test_versions(pattern):
    assert pattern not in core_10x.__version__
    assert pattern not in py10x_core.__version__
