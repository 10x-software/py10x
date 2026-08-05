"""Manual performance comparison: PostgresStore vs MongoStore, same dataset shape.

Covers write, point-read, filtered search (before/after an index), a range query, and —
since ``keep_history=True`` is a Traitable-level feature with its own automatically
created ``(_traitable_id, _at)`` index (see ``TraitableHistory.s_indices`` in
``core_10x/traitable.py``) — history-revision writes and an indexed history query.

Requires a reachable trust-auth Postgres on 5432 and a reachable Mongo on 27017 (see
INSTALLATION.md). Creates/drops its own throwaway collections; does not touch existing data.

``N_DOCS`` goes through the full Traitable stack (construct, ``set_values``, ``save``) to
measure realistic single-op write latency and defaults small, since that path is slow
(well under 100 docs/sec measured on this machine — 1M docs would be tens of minutes;
wrapping many saves in one ``store.transaction()`` was tried and didn't meaningfully help,
confirming the cost is per-object Traitable/kernel overhead, not commit round-trips).
``READ_N_DOCS`` is loaded via the raw ``TsCollection.save_new`` path instead — batched
inside one ``store.transaction()`` — to actually skip that overhead and give the
read/search/index phases a realistic-scale dataset without an N_DOCS-slow load. Note
``payload`` is a JSON *string* trait, not a ``dict`` trait: a dict-trait bulk load was
tried first and broke ``BenchDoc.load()`` afterwards, because raw ``save_new`` skips the
ORM's dict-trait wire wrapping. Bump ``READ_N_DOCS`` for a large-scale read comparison;
index-vs-no-index effects become far more visible at scale.

Run from repo root::

    uv run --no-sync python infra_10x/manual_tests/postgres_vs_mongo_perf_test.py
"""

from __future__ import annotations

import json
import random

N_DOCS = 1_000
READ_N_DOCS = 20_000  # bulk-loaded; bump toward 1_000_000 for a large-scale read/search comparison
N_CATEGORIES = 30
SAMPLE_SIZE = 500  # point-read / search sample
HISTORY_ENTITIES = min(500, N_DOCS // 10)
HISTORY_REVISIONS = 5

if __name__ == '__main__':
    from datetime import datetime, timezone

    import uuid6
    from core_10x.logger import PerfTimer
    from core_10x.trait_definition import T
    from core_10x.trait_filter import GT, f
    from core_10x.traitable import Traitable
    from core_10x.traitable_id import ID
    from core_10x.ts_store import TsStore

    random.seed(0)

    class BenchDocBase(Traitable, custom_collection=True, keep_history=False):
        doc_id: str = T(T.ID)
        category: str = T()
        score: float = T()
        payload: str = T()  # JSON text — see module docstring for why not a dict trait

    class BenchLogBase(Traitable, custom_collection=True, keep_history=True):
        doc_id: str = T(T.ID)
        value: int = T()

    BenchDoc = type(f'BenchDoc#{uuid6.uuid7().hex}', (BenchDocBase,), {'__module__': __name__})
    BenchLog = type(f'BenchLog#{uuid6.uuid7().hex}', (BenchLogBase,), {'__module__': __name__})

    def make_payload(i: int) -> str:
        return json.dumps({'tags': [f'tag{i % 5}', f'tag{(i + 1) % 5}'], 'meta': {'source': 'bench', 'weight': round(random.random(), 4)}})

    def fmt_rate(n: int, ns: int) -> str:
        secs = ns / 1e9
        return f'{secs:7.3f}s  {n / secs:10,.0f}/s' if secs > 0 else f'{0:7.3f}s  {"n/a":>10}'

    def bench_backend(uri: str, label: str) -> dict[str, str]:
        store = TsStore.instance_from_uri(uri, _cache=False)
        results: dict[str, str] = {}
        doc_coll_name = f'bench_doc_{uuid6.uuid7().hex}'
        log_coll_name = f'bench_log_{uuid6.uuid7().hex}'

        with store:
            categories = [f'cat_{i}' for i in range(N_CATEGORIES)]
            ids = [f'd{i}' for i in range(N_DOCS)]

            # --- write ---------------------------------------------------------------
            with PerfTimer() as t:
                for i, doc_id in enumerate(ids):
                    doc = BenchDoc(doc_id=doc_id, _collection_name=doc_coll_name)
                    doc.set_values(category=categories[i % N_CATEGORIES], score=random.random() * 1000, payload=make_payload(i))
                    doc.save().throw()
            results['write'] = fmt_rate(N_DOCS, t.elapsed)

            # --- bulk load: raw save_new (skips per-object Traitable/kernel overhead),
            # batched inside one transaction, so the read/search phases below get a
            # realistic-scale dataset fast. See module docstring for why `payload` is a
            # JSON string trait rather than a dict trait (dict-typed traits need the ORM's
            # wire wrapping to read back correctly; plain strings round-trip as-is).
            read_ids = [f'r{i}' for i in range(READ_N_DOCS)]
            raw_coll = store.collection(doc_coll_name, BenchDoc.s_dir)
            with PerfTimer() as t, store.transaction():
                for i, doc_id in enumerate(read_ids):
                    raw_coll.save_new(
                        {'_id': doc_id, 'category': categories[i % N_CATEGORIES], 'score': random.random() * 1000, 'payload': make_payload(i)}
                    )
            results['bulk load'] = fmt_rate(READ_N_DOCS, t.elapsed)

            # --- point read ------------------------------------------------------------
            sample_ids = random.sample(read_ids, min(SAMPLE_SIZE, READ_N_DOCS))
            with PerfTimer() as t:
                for doc_id in sample_ids:
                    BenchDoc.load(ID(doc_id, doc_coll_name))
            results['point read'] = fmt_rate(len(sample_ids), t.elapsed)

            # --- search: unindexed -----------------------------------------------------
            target_category = categories[0]
            with PerfTimer() as t:
                for _ in range(10):
                    BenchDoc.load_many(f(category=target_category), _coll_name=doc_coll_name)
            results['search (no index)'] = fmt_rate(10, t.elapsed)

            # --- create index, then re-run the same search + a range query -------------
            coll = BenchDoc.collection(doc_coll_name)
            coll.create_index('idx_category', 'category')
            coll.create_index('idx_score', 'score')

            with PerfTimer() as t:
                for _ in range(10):
                    BenchDoc.load_many(f(category=target_category), _coll_name=doc_coll_name)
            results['search (indexed)'] = fmt_rate(10, t.elapsed)

            with PerfTimer() as t:
                for _ in range(10):
                    BenchDoc.load_many(f(score=GT(500.0)), _coll_name=doc_coll_name)
            results['range search (indexed)'] = fmt_rate(10, t.elapsed)

            # --- history: build revisions, then query the auto-indexed history ----------
            history_ids = ids[:HISTORY_ENTITIES]
            with PerfTimer() as t:
                for doc_id in history_ids:
                    log = BenchLog(doc_id=doc_id, _collection_name=log_coll_name)
                    log.set_values(value=0)
                    log.save().throw()
                    for rev in range(1, HISTORY_REVISIONS + 1):
                        log.set_values(value=rev)
                        log.save().throw()
            results['history writes'] = fmt_rate(HISTORY_ENTITIES * (HISTORY_REVISIONS + 1), t.elapsed)

            with PerfTimer() as t:
                for doc_id in random.sample(history_ids, min(SAMPLE_SIZE, HISTORY_ENTITIES)):
                    BenchLog.history(_filter=f(_traitable_id=doc_id), _collection_name=log_coll_name)
            results['history query (indexed)'] = fmt_rate(min(SAMPLE_SIZE, HISTORY_ENTITIES), t.elapsed)

            store.delete_collection(doc_coll_name)
            store.delete_collection(f'{doc_coll_name}#history')
            store.delete_collection(log_coll_name)
            store.delete_collection(f'{log_coll_name}#history')

        return results

    backends = [
        ('postgres', 'postgresql://localhost:5432/postgres'),
        ('mongo', 'mongodb://localhost:27017/perf_test'),
    ]

    print(
        f'N_DOCS={N_DOCS}  N_CATEGORIES={N_CATEGORIES}  SAMPLE_SIZE={SAMPLE_SIZE}  '
        f'HISTORY_ENTITIES={HISTORY_ENTITIES}  HISTORY_REVISIONS={HISTORY_REVISIONS}'
    )
    print(f'started {datetime.now(timezone.utc).isoformat()}')

    all_results: dict[str, dict[str, str]] = {}
    for label, uri in backends:
        print(f'\n--- {label} ---')
        all_results[label] = bench_backend(uri, label)
        for phase, rate in all_results[label].items():
            print(f'  {phase:<26} {rate}')

    print(f'\n{"phase":<26} {"postgres":>20} {"mongo":>20}')
    print('-' * 68)
    phases = list(next(iter(all_results.values())).keys()) if all_results else []
    for phase in phases:
        row = ' '.join(f'{all_results[label].get(phase, "n/a"):>20}' for label, _ in backends)
        print(f'{phase:<26} {row}')
