# py10x-kernel-test

Minimal uv harness for running the real core tests against editable builds of `py10x-kernel`, `py10x-infra` and `py10x-core` from this repo.

## First-time / fresh-start preparation (run once)

```bash
uv venv --clear
uv pip install -e "../../..[dev]"
```

After that, `uv run` syncs the rest automatically.

`py10x-kernel` and `py10x-infra` build without isolation, so their toolchain (scikit-build-core,
cmake, ninja, ...) comes first, from `py10x-core[dev]`. They build into this directory's `.venv` 
(so `--clear` also resets the builds), and are rebuilt (incrementally) on every `uv run`.

## Run

```bash
uv run python ../../core_10x/tests/test.py
```
