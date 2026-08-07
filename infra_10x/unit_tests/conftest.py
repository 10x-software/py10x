from __future__ import annotations

from contextlib import nullcontext
from typing import NamedTuple

import pytest
from core_10x.environment_variables import EnvVars
from core_10x.named_constant import NamedConstant
from core_10x.testlib import test_databases
from core_10x.testlib.strict import need
from core_10x.ts_store import TsStore
from infra_10x import MongoCollectionHelper
from infra_10x.testlib.mongo_collection_helper import MongoCollectionHelperStub


class Backend(NamedTuple):
    helper_flags: tuple[bool, ...]  # -- one fixture param per flag; True → patch in the py MongoCollectionHelper
    hard_require: bool  # -- True → fail (not skip) when the server is unreachable


class TEST_TS_STORE(NamedConstant):
    # URIs are per-session databases — see core_10x/testlib/test_databases.py.
    MONGODB = Backend((True, False), True)
    POSTGRESQL = Backend((False,), False)


@pytest.fixture(
    params=[
        pytest.param((backend, py_helper), id=f'{backend.name.lower()}{"-py-helper" if py_helper else ""}')
        for backend in TEST_TS_STORE.s_dir.values()
        for py_helper in backend.value.helper_flags
    ]
)
def ts_instance(mocker, request, live_store):
    backend = request.param[0]
    instance = live_store(backend.name)
    if instance is None:
        msg = f'{backend.label} not running (at {test_databases.test_uri(backend.name)})'
        if backend.value.hard_require:
            pytest.fail(msg)
        need(False, msg)
    assert instance is not None

    # Mongo/DuckDB ``auth_user`` is Resource.username; Postgres stamps SQL ``current_user``.
    if backend == TEST_TS_STORE.MONGODB:
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
def postgres_store(live_store):
    store_protocol = TEST_TS_STORE.POSTGRESQL.name
    store = live_store(store_protocol)
    need(store is not None, f'{store_protocol} not running (at {test_databases.test_uri(store_protocol)})')
    return store


@pytest.fixture(scope='module', autouse=True)
def clear_ts_store_instances():
    assert not TsStore.s_instances
    yield
    TsStore.s_instances.clear()
