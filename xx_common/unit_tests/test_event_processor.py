from datetime import datetime, timedelta

import pytest

from core_10x.environment_variables import EnvVars
from core_10x.traitable import T, Traitable
from xx_common.event import Event
from xx_common.event_processor import EventProcessor


def _clear_main_store_caches() -> None:
    object.__getattribute__(EnvVars, 'main_ts_store_uri').fget.clear()
    object.__getattribute__(Traitable, 'main_store').__func__.clear()


class Tick(Event):
    n: int = T(0)


class Counter(EventProcessor, inputs=(Tick,), outputs=()):
    total: int = T(0)

    def Tick_process(self, event: Tick):
        self.total = self.total + event.n


@pytest.fixture
def event_store(monkeypatch, mocker):
    _clear_main_store_caches()
    monkeypatch.setenv('XX_MAIN_TS_STORE_URI', 'testdb://localhost/event_processor')
    monkeypatch.setenv('XX_VAULT_URI', 'testdb://localhost/vault')

    # Monotonic store clock so event _at values sit strictly below each watermark query.
    clock = [datetime(2026, 6, 1, 12, 0, 0)]

    def utcnow():
        clock[0] += timedelta(milliseconds=10)
        return clock[0]

    mock_dt = mocker.patch('core_10x.testlib.test_store.datetime', autospec=True)
    mock_dt.utcnow.side_effect = utcnow
    mock_dt.now.side_effect = utcnow
    mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

    store = Traitable.main_store()
    yield store
    for name in store.collection_names():
        store.delete_collection(name)
    _clear_main_store_caches()


def test_process_pending_events_loads_and_dispatches(event_store):
    Tick(n=1).save().throw()
    Tick(n=2).save().throw()

    proc = Counter()
    assert proc.process_pending_events() == 2
    assert proc.total == 3

    assert proc.process_pending_events() == 0
    assert proc.total == 3
