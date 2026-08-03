from __future__ import annotations

import getpass
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
    POSTGRES = [f'postgresql://{getpass.getuser()}@localhost:5432/postgres', (False,), False]


@pytest.fixture(scope='session')
def ts_backends() -> dict[str, TsStore | None]:
    """Probe + build each TEST_TS_STORE backend once; keep stores out of ``s_instances``.

    Isolation clears ``@cache`` (and ``s_instances``) every test. Session-scoped stores
    avoid re-probing Mongo (open+close → dead weakref proxies) and rebuilding connections.
    ``s_instances`` is only a cache — assert empty, populate while connecting, then clear
    so module fixtures can keep treating it as empty between tests.
    """
    assert not TsStore.s_instances
    backends: dict[str, TsStore | None] = {}
    for backend in TEST_TS_STORE.s_dir.values():
        spec = TsStore.spec_from_uri(backend.value[0])
        if not spec.resource_class.is_running_with_auth(spec.hostname(), spec.port())[0]:
            backends[backend.name] = None
            continue
        backends[backend.name] = TsStore.instance_from_uri(backend.value[0])
    TsStore.s_instances.clear()
    return backends


@pytest.fixture(
    params=[
        pytest.param((backend, py_helper), id=f'{backend.name.lower()}{"-py-helper" if py_helper else ""}')
        for backend in TEST_TS_STORE.s_dir.values()
        for py_helper in backend.value[1]
    ]
)
def ts_instance(mocker, request, ts_backends):
    backend = request.param[0]
    instance = ts_backends[backend.name]
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
    store = ts_backends[TEST_TS_STORE.POSTGRES.name]
    need(store is not None, f'{TEST_TS_STORE.POSTGRES.label} not running (at {TEST_TS_STORE.POSTGRES.value[0]})')
    return store


@pytest.fixture(scope='module', autouse=True)
def clear_ts_store_instances():
    assert not TsStore.s_instances
    yield
    TsStore.s_instances.clear()
