import py10x_infra
import pytest

import infra_10x


@pytest.mark.parametrize('pattern', ['0.0.0', 'unknown'])
def test_versions(pattern):
    assert pattern not in infra_10x.__version__
    assert pattern not in py10x_infra.__version__
