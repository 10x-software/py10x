"""Manual performance comparison: Python stub vs full-C++ MongoCollectionHelper.

Both paths pop ``_id``/``_rev`` into ``filter`` and build the pipeline
(the production / ``save()`` contract).

Reports median ± half-range over ``NUM_TRIALS`` (paths interleaved each trial).

No MongoDB connection is required.

Run from repo root::

    uv run --no-sync python infra_10x/manual_tests/mongo_helper_perf_test.py
"""

if __name__ == '__main__':
    from statistics import median, stdev

    from core_10x.logger import PerfTimer
    from infra_10x.testlib.mongo_collection_helper import MongoCollectionHelperStub
    from py10x_infra import MongoCollectionHelper

    NUM_ITERS = 50_000
    WARMUP = 1_000
    NUM_TRIALS = 11

    payloads = {
        'small': dict(_id='AAAA', _rev=10, name='test', age=60),
        'medium': dict(
            _id='BBBB',
            _rev=42,
            name='widget',
            age=30,
            city='NYC',
            country='US',
            score=99.5,
            active=True,
            tag='alpha',
            notes='hello',
        ),
        'large': {
            '_id': 'CCCC',
            '_rev': 100,
            **{f'field_{i}': i for i in range(50)},
        },
    }

    def once(helper, payload: dict) -> tuple[dict, dict, list]:
        data = dict(payload)
        filt: dict = {}
        pipe: list = []
        helper.prepare_filter_and_pipeline(data, filt, pipe)
        return data, filt, pipe

    def bench(helper, payload: dict, n: int) -> float:
        with PerfTimer() as t:
            for _ in range(n):
                once(helper, payload)
        return t.elapsed / n

    def fmt(samples: list[float]) -> str:
        med = median(samples)
        lo, hi = min(samples), max(samples)
        return f'{med:.1f}±{(hi - lo) / 2:.1f}'

    paths = (
        ('a) pure py', MongoCollectionHelperStub),
        ('b) full cxx', MongoCollectionHelper),
    )

    print(f'iters={NUM_ITERS}  warmup={WARMUP}  trials={NUM_TRIALS}')
    print('values: median±half-range ns/call; paths interleaved each trial')
    print(
        f'{"payload":<10} {"fields":>6}'
        f' {"a) pure py":>16} {"b) full cxx":>16}'
        f' {"a/b":>8}'
    )
    print('-' * 60)

    for name, payload in payloads.items():
        ref_data, ref_filt, ref_pipe = once(MongoCollectionHelperStub, payload)
        data, filt, pipe = once(MongoCollectionHelper, payload)
        assert filt == ref_filt, f'{name}: filter mismatch'
        assert pipe == ref_pipe, f'{name}: pipeline mismatch'
        assert data == ref_data, f'{name}: data mismatch'

        for _, helper in paths:
            bench(helper, payload, WARMUP)

        samples = {label: [] for label, _ in paths}
        for _ in range(NUM_TRIALS):
            for label, helper in paths:
                samples[label].append(bench(helper, payload, NUM_ITERS))

        a = median(samples['a) pure py'])
        b = median(samples['b) full cxx'])
        n_fields = len(payload) - 2

        print(
            f'{name:<10} {n_fields:6d}'
            f' {fmt(samples["a) pure py"]):>16}'
            f' {fmt(samples["b) full cxx"]):>16}'
            f' {a / b:8.2f}x'
        )
        print(
            f'{"":<10} {"":>6}'
            f' {"(stdev)":>16}'
            f' {stdev(samples["a) pure py"]):>16.1f}'
            f' {stdev(samples["b) full cxx"]):>16.1f}'
        )
