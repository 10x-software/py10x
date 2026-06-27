from datetime import datetime, timedelta, timezone

import pytest

from core_10x.environment_variables import EnvVars
from core_10x.traitable import T, Traitable
from xx_common.event import Event
from xx_common.event_processor import EventProcessor


def _clear_main_store_caches() -> None:
    object.__getattribute__(EnvVars, 'main_ts_store_uri').fget.clear()
    object.__getattribute__(Traitable, 'main_store').__func__.clear()


class Ping(Event):
    n: int = T(0)


class PingCounter(EventProcessor, inputs=(Ping,), outputs=()):
    total: int = T(0)

    def Ping_process(self, event: Ping):
        self.total = self.total + event.n


class Pong(Event):
    n: int = T(0)

class  PongCounter(EventProcessor, inputs=(Pong,), outputs=()):
    total: int = T(0)

    def Pong_process(self, event: "Pong"):
        self.total = self.total + event.n


@pytest.fixture
def event_store(monkeypatch, mocker):
    _clear_main_store_caches()
    monkeypatch.setenv('XX_MAIN_TS_STORE_URI', 'duckdb://localhost/event_processor')
    monkeypatch.setenv('XX_VAULT_URI', 'duckdb://localhost/vault')

    # Monotonic store clock so event _at values sit strictly below each watermark query.
    clock = [datetime(2026, 6, 1, 12, 0, 0)]

    def now(tz):
        assert tz == timezone.utc
        clock[0] += timedelta(milliseconds=10)
        return clock[0]

    from infra_10x.duckdb_store import DuckDbStore
    mocker.patch.object(DuckDbStore, 'server_time', lambda self: now(timezone.utc))

    store = Traitable.main_store()
    yield store
    for name in store.collection_names():
        store.delete_collection(name)
    _clear_main_store_caches()


def test_process_pending_events_loads_and_dispatches(event_store):
    Ping(n=1).save().throw()
    Ping(n=2).save().throw()

    proc = PingCounter()
    assert proc.process_pending_events() == 2
    assert proc.total == 3

    assert proc.process_pending_events() == 0
    assert proc.total == 3


def test_string_annotated_process_method_resolves(event_store):
    Pong(n=4).save().throw()
    Pong(n=5).save().throw()

    proc =  PongCounter()
    assert proc.process_pending_events() == 2
    assert proc.total == 9
