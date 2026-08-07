"""Drop test databases left behind by killed pytest sessions.

Each pytest process creates its own ``py10x_test_*`` database on Postgres and Mongo and drops
it at the end (see ``core_10x/testlib/test_databases.py``). A session killed before teardown —
Ctrl-C, a crash, a CI timeout — leaves its database behind. This is the broom for those.

Usage (from repo root, venv prepared)::

    uv run --no-sync xx-test-db-clean list    # what is there
    uv run --no-sync xx-test-db-clean drop    # drop it

Dropping is not reversible, hence a separate command rather than a flag on ``list``. Only names
starting with ``py10x_test`` are ever candidates — but a *running* session's database matches
too, so do not ``drop`` while tests are in flight elsewhere.
"""

from __future__ import annotations

from core_10x.rc import RC, RC_TRUE
from core_10x.testlib.test_databases import ALL_STORE_PROTOCOLS, TEST_DB_PREFIX, test_uri
from core_10x.trait_definition import RT
from core_10x.traitable_cli import TraitableCli
from core_10x.ts_store import TsStore

# Before per-session databases, tests wrote into these fixed Mongo databases and into the
# Postgres server default. Only `legacy` looks at them.
LEGACY_MONGO_DBS = ('test_db', 'test_filters_mongo', 'perf_test')
LEGACY_PG_DB = 'postgres'


class TestDbCleanCli(TraitableCli):
    """Leftover test databases on the servers the suite uses.

    Usage:
    xx-test-db-clean list      report ``py10x_test*`` databases
    xx-test-db-clean drop      drop them
    xx-test-db-clean legacy    one-time: test data predating per-session databases
    """

    def _found(self) -> list[tuple[TsStore, list[str]]]:
        """``(server_store, names)`` per reachable server; an unreachable one is reported, not fatal."""
        out = []
        for store_protocol in ALL_STORE_PROTOCOLS:
            server_uri = test_uri(store_protocol, session_db='')
            try:
                store = TsStore.instance_from_uri(server_uri)
                names = store.list_databases(TEST_DB_PREFIX)
            except Exception as e:  # noqa: BLE001 -- a down server is not an error for a cleanup tool
                print(f'{server_uri}\n  skipped ({type(e).__name__}: {str(e).strip().splitlines()[0]})')
                continue
            print(f'{server_uri}\n  {len(names)} test database(s)' + (f': {names}' if names else ''))
            out.append((store, names))
        return out


class List(TestDbCleanCli, _command='list'):
    """Report what would be dropped."""

    def run(self) -> RC:
        total = sum(len(names) for _, names in self._found())
        print(f'\n{total} database(s). `xx-test-db-clean drop` to remove them.')
        return RC_TRUE


class Drop(TestDbCleanCli, _command='drop'):
    """Drop every ``py10x_test*`` database on each reachable server."""

    def run(self) -> RC:
        total = sum(store.delete_database(name) for store, names in self._found() for name in names)
        print(f'\n{total} database(s) dropped.')
        return RC_TRUE


class Legacy(TestDbCleanCli, _command='legacy'):
    """One-time: drop test data from before per-session databases existed.

    Mongo: the whole fixed test databases. Postgres: only collections in the server default,
    which ``collection_names`` already limits to tables carrying the collection layout — so
    tables of your own in that database are never candidates.
    """

    drop: bool = RT(False)

    def _report(self, uri: str) -> list[str]:
        names = TsStore.instance_from_uri(uri).collection_names()
        print(f'{uri}\n  {len(names)} collection(s)')
        return names

    def run(self) -> RC:
        pg_uri = test_uri('postgresql', session_db=LEGACY_PG_DB)
        if self.drop:
            store = TsStore.instance_from_uri(pg_uri)
            for name in self._report(pg_uri):
                store.delete_collection(name)
        else:
            self._report(pg_uri)

        for dbname in LEGACY_MONGO_DBS:
            uri = test_uri('mongodb', session_db=dbname)
            if not self._report(uri):
                continue
            if self.drop:
                TsStore.instance_from_uri(test_uri('mongodb', session_db='')).delete_database(dbname)

        print('\n' + ('dropped.' if self.drop else '`xx-test-db-clean legacy --drop` to remove.'))
        return RC_TRUE


def main() -> int:
    rc, inst = TestDbCleanCli.from_command_line()
    if not rc:
        print(rc.error())
        return 2
    rc = inst.run()
    if not rc:
        print(rc.error())
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
