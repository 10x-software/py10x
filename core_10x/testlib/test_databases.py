"""Per-session databases for live-store tests.

Every pytest process gets its **own** database on each backend, created at session start and
dropped at the end (wired in the root ``conftest.py``).

Why not share one test database and clean up what a run created: two sessions against the
same server — two terminals, or a local run overlapping a CI agent — interleave. Any
"snapshot at start, remove the difference at the end" scheme then has the first session to
finish deleting the second session's live data out from under it. Session-scoped databases
remove the shared state instead of trying to arbitrate it.

It also makes leak detection exact rather than heuristic: the database starts empty, so
whatever is still in it at teardown was leaked by a fixture, with no baseline to diff
against. See ``conftest.py``.

Set ``XX_TEST_DB`` to pin a fixed name when you want to inspect a database after a run
(it is then *not* dropped — the run that created it is the one that drops it).
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING

import pytest
import uuid6

from core_10x.resource import Resource
from core_10x.ts_store import TsStore
from core_10x.ts_store_type import TS_STORE_TYPE

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

# -- Every database this suite creates starts with this, so ``xx-test-db-clean`` can find the
# -- ones a killed session never got to drop. Keep in sync with ``dev_10x/db_clean.py``.
TEST_DB_PREFIX = 'py10x_test'

# -- One database name per pytest process (module import happens once per process). Timestamp
# -- first so a leftover is obviously old at a glance and names sort chronologically; pid makes
# -- it traceable to the run that made it. The tail is uuid7's *random* end, not its leading
# -- millisecond timestamp — two processes starting in the same millisecond share that exactly.
SESSION_DB: str = os.environ.get('XX_TEST_DB') or f'{TEST_DB_PREFIX}_{datetime.now():%Y%m%d_%H%M%S}_{os.getpid()}_{uuid6.uuid7().hex[-4:]}'

# -- True when the name was pinned by the caller, who then owns its lifecycle.
SESSION_DB_IS_PINNED: bool = bool(os.environ.get('XX_TEST_DB'))

POSTGRES_SERVER = 'postgresql://localhost:5432/'
MONGO_SERVER = 'mongodb://localhost:27017/'


def test_uri(store_protocol: str, session_db: str = SESSION_DB) -> str:
    """URI for ``session_db`` on localhost (using ``store_protocol``'s default port). ``session_db=''`` gives the server."""
    # Lowercased: callers pass TS_STORE_TYPE member names (MONGODB), but a URI scheme is
    # matched case-sensitively by the driver parsers.
    return f'{store_protocol.lower()}://localhost/{session_db}'


@pytest.fixture(scope='session')
def live_store() -> Iterator[Callable[[str, str], TsStore | None]]:
    """``(protocol[, custom_db]) -> store``, or ``None`` when that backend is not running.

    Owns every database it creates: this session's by default, or ``custom_db`` when a test
    needs a *second* store on the same backend (a store-wide ``copy_to`` needs source and
    target to be different stores). All are dropped when the session ends.
    """
    from core_10x.ts_store import TsStore

    stores = {}
    created = set()

    def test_store(store_protocol: str, custom_db: str = '') -> TsStore | None:
        dbname = custom_db or SESSION_DB
        if (uri := test_uri(store_protocol, dbname)) not in stores:
            if not TsStore.is_running_with_auth_from_uri(uri)[0]:
                stores[uri] = None
            else:
                stores[uri] = TsStore.instance_from_uri(uri, _cache=False, _create_if_needed=True)
                created.add((Resource.uri_no_dbname(uri), dbname))
        return stores[uri]

    yield test_store

    for uri, dbname in iter(created):
        if dbname == SESSION_DB and SESSION_DB_IS_PINNED:
            continue
        # From a store on the server default: a store cannot drop the database it is on.
        TsStore.instance_from_uri(uri, _cache=False).delete_database(dbname)
