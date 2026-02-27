import pytest

from core_10x.environment_variables import EnvVars


@pytest.fixture(params=[True, False], ids=['with_transactions', 'without_transactions'])
def with_transactions(request, ts_instance, monkeypatch):
    use_transactions = request.param
    if use_transactions and not ts_instance.supports_transactions():
        pytest.skip('Store does not support transactions')

    monkeypatch.setenv('XX_USE_TS_STORE_TRANSACTIONS', '1' if use_transactions else '0')
    object.__getattribute__(EnvVars, 'use_ts_store_transactions').fget.clear()
    yield use_transactions
