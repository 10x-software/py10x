from datetime import datetime, timedelta

import pytest

from core_10x.traitable import T
from xxcommon.event import Event
from xxcommon.event_processor import EventProcessor


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


def test_event_immutable():
    assert Event.s_immutable
    assert Event.s_history_class is None

    assert Pong.s_immutable
    assert Pong.s_history_class is None

@pytest.fixture
def event_store(mocker):
    # Monotonic store clock so event _at values sit strictly below each watermark query.
    # TS_TIME is stamped in SQL via _server_time_col_sql_expr (not Python server_time alone).
    clock = [datetime(2026, 6, 1, 12, 0, 0)]

    def server_time_sql(self):
        clock[0] += timedelta(milliseconds=10)
        return f"CAST('{clock[0].strftime('%Y-%m-%d %H:%M:%S.%f')}' AS TIMESTAMP)"

    from infra_10x.duckdb_store import DuckDbStore
    mocker.patch.object(DuckDbStore, '_server_time_col_sql_expr', server_time_sql)

    store = DuckDbStore()
    with store:
        yield


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
