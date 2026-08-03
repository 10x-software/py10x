from __future__ import annotations

from contextlib import nullcontext

import pytest
from core_10x.environment_variables import EnvVars
from core_10x.named_constant import NamedConstant
from core_10x.testlib.strict import need
from core_10x.ts_store import TsStore
from infra_10x import MongoCollectionHelper
from infra_10x.testlib.mongo_collection_helper import MongoCollectionHelperStub


class TEST_TS_STORE(NamedConstant):
    # Example with X509 auth (replace with your URI; do not commit real hostnames or paths):
    # MONGO = ('MongoDB', ('mongodb+srv://HOST/?authMechanism=MONGODB-X509&...', (True, False)))
    MONGO = ['mongodb://localhost:27017/test_db', (True, False), True]
    POSTGRES = ['postgresql://localhost:5432/postgres', (False,), False]


@pytest.fixture(scope='session')
def ts_backends() -> dict[str, TsStore]:
    """Probe + build each reachable TEST_TS_STORE backend once (``_cache=False``)."""
    return {
        backend.name: TsStore.instance_from_uri(backend.value[0], _cache=False)
        for backend in TEST_TS_STORE.s_dir.values()
        if TsStore.is_running_with_auth_from_uri(backend.value[0])[0]
    }


@pytest.fixture(
    params=[
        pytest.param((backend, py_helper), id=f'{backend.name.lower()}{"-py-helper" if py_helper else ""}')
        for backend in TEST_TS_STORE.s_dir.values()
        for py_helper in backend.value[1]
    ]
)
def ts_instance(mocker, request, ts_backends):
    backend = request.param[0]
    instance = ts_backends.get(backend.name)
    if not backend.value[2]:
        need(instance is not None, f'{backend.label} not running (at {backend.value[0]})')
    assert instance is not None

    instance.username = 'test_user'
    if not instance.supports_transactions():
        # Under XX_TEST_STRICT a missing replica set is a CI provisioning failure.
        if EnvVars.test_strict:
            instance.transaction = lambda *args: pytest.fail(
                f'XX_TEST_STRICT set but {backend.label} lacks transactions (replica set not provisioned?)'
            )
        else:
            instance.transaction = lambda *args: nullcontext()
    if request.param[1]:
        # Intentionally materialize metaclass __annotations__ to simulate prior
        # access on pybind11_type and keep this path covered.
        _ = type(MongoCollectionHelper).__annotations__
        mock = mocker.patch('infra_10x.MongoCollectionHelper')
        mock.value = MongoCollectionHelperStub
    return instance


@pytest.fixture
def postgres_store(ts_backends):
    store = ts_backends.get(TEST_TS_STORE.POSTGRES.name)
    need(store is not None, f'{TEST_TS_STORE.POSTGRES.label} not running (at {TEST_TS_STORE.POSTGRES.value[0]})')
    return store


@pytest.fixture(scope='module', autouse=True)
def clear_ts_store_instances():
    assert not TsStore.s_instances
    yield
    TsStore.s_instances.clear()
