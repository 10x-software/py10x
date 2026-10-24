"""Microbenchmark of hot py10x_kernel call paths (trait get/set, ID, float/enum args), e.g. to compare pybind11 versions.

Benchmark a Release kernel (the dev env builds Debug), e.g. from cxx10x/tests/py10x_kernel_test:
    uv venv --clear && uv pip install --group ../../../pyproject.toml:build && uv sync -C cmake.build-type=Release
    .venv/bin/python ../../../core_10x/manual_tests/kernel_call_bench.py <label> [out.json]
Repeat for the other build (alternate the two on an idle machine: absolute numbers drift with load), then:
    python kernel_call_bench.py --compare base.json new.json
"""

import json
import sys
import timeit


def bench(label: str, out_path: str | None):
    from datetime import date

    from core_10x.environment_variables import EnvVars

    EnvVars.traitable_store_uri = ''

    import py10x_kernel

    from core_10x.code_samples.person import Person
    from core_10x.exec_control import CACHE_ONLY

    with CACHE_ONLY():
        p = Person(first_name='Ann', last_name='Lee')
        p.weight_lbs = 150.0
        p.dob = date(1980, 1, 1)
        trait_w = p.T.weight_lbs
        letters = 'abcdefghij'  # -- first_name must be alphabetic
        people = [Person(first_name=f'N{letters[i % 10]}{letters[i // 10 % 10]}{letters[i // 100]}', last_name='Bulk') for i in range(1000)]
        for i, q in enumerate(people):
            q.weight_lbs = float(i)

        curve = py10x_kernel.BCurve([float(i) for i in range(100)], [float(i * i) for i in range(100)])
        lin, prev = py10x_kernel.IPKind.LINEAR, py10x_kernel.IPKind.PREVIOUS
        val = [150.0]

        def set_attr():
            val[0] += 1.0
            p.weight_lbs = val[0]

        def set_value():
            val[0] += 1.0
            p.set_value('weight_lbs', val[0])

        def rt_getter_recompute():
            p.invalidate_value('full_name')
            return p.full_name

        cases = {  # -- name: (callable, calls per timing loop)
            'attr get  p.weight_lbs':               (lambda: p.weight_lbs, 200_000),
            'kernel    p.get_value(name)':          (lambda: p.get_value('weight_lbs'), 200_000),
            'kernel    p.get_trait_value(trait)':   (lambda: p.get_trait_value(trait_w), 200_000),
            'attr set  p.weight_lbs = x':           (set_attr, 100_000),
            'kernel    p.set_value(name, x)':       (set_value, 100_000),
            'RT getter invalidate + p.full_name':   (rt_getter_recompute, 50_000),
            'ID        p.id_value()':               (lambda: p.id_value(), 200_000),
            'ID        p.id()':                     (lambda: p.id(), 200_000),
            'ID        Person(existing ID)':        (lambda: Person(first_name='Ann', last_name='Lee'), 20_000),
            'float arg curve.value(t)':             (lambda: curve.value(42.5), 200_000),
            'enum arg  curve.set_ip_kind(e)':       (lambda: curve.set_ip_kind(lin), 200_000),
            'enum op   IPKind == IPKind':           (lambda: lin == prev, 200_000),
            'bulk      calc_values(1000 objs)':     (lambda: py10x_kernel.BTraitable.calc_values(people, 'weight_lbs'), 1_000),
        }

        for fn, _ in cases.values():  # -- warm-up
            fn()

        results = {}
        for name, (fn, number) in cases.items():
            results[name] = min(timeit.Timer(fn).repeat(repeat=7, number=number)) / number * 1e9
            print(f'{label:>8}  {name:<40} {results[name]:9.1f} ns/call', flush=True)

    if out_path:
        with open(out_path, 'w') as f:
            json.dump({'label': label, 'kernel': py10x_kernel.__file__, 'ns': results}, f, indent=1)


def compare(base_path: str, new_path: str):
    with open(base_path) as f:
        base = json.load(f)
    with open(new_path) as f:
        new = json.load(f)
    print(f'{"case":<40} {base["label"]:>10} {new["label"]:>10} {"change":>8}')
    for name, b in base['ns'].items():
        n = new['ns'][name]
        print(f'{name:<40} {b:10.1f} {n:10.1f} {100 * (n / b - 1):+7.1f}%')


if __name__ == '__main__':
    if sys.argv[1:2] == ['--compare']:
        compare(sys.argv[2], sys.argv[3])
    else:
        bench(sys.argv[1] if len(sys.argv) > 1 else 'kernel', sys.argv[2] if len(sys.argv) > 2 else None)
