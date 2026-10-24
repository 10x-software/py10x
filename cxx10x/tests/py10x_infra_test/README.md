# py10x-infra-test

Minimal uv harness for running the real infra tests against editable builds of `py10x-kernel`, `py10x-infra` and `py10x-core` from this repo.

## First-time / fresh-start preparation (run once)

```bash
uv venv --clear
uv pip install --python .venv --group ../../../pyproject.toml:build
```

After that, `uv run` syncs the rest automatically.

`--python .venv`: this directory's venv, whatever venv is active - `uv pip` would otherwise install into
an activated one (e.g. py10x's own), while `uv run` / `uv sync` always use this project's `.venv`.

`py10x-kernel` and `py10x-infra` build without isolation, so their toolchain (scikit-build-core,
cmake, ninja, ...) comes first, from py10x's `build` dependency group. They build into this
directory's `.venv` (so `--clear` also resets the builds), and are rebuilt (incrementally) on every
`uv run`.

## Run

```bash
uv run python ../../infra_10x/tests/test.py
```
