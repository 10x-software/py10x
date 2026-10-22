# cross_module_test

This is a small self-contained test package (separate `pyproject.toml` + scikit-build-core + the shared `cmake/XX_pybind11_add_module.cmake`).

It demonstrates using py10x-kernel types (including BTraitable*) from another extension: C++ getters via s_cxx_mixins and direct calls to C++ methods. It works when the kernel and extension share the same build configuration (identical PYBIND11_INTERNALS_ID).

The s_cxx_mixins demonstration is in `test.py` (function `test_with_s_cxx_mixins`).

This is the canonical test for the PY10X_API + shared-build cross-module story.

## First-time / fresh-start preparation (run once)

```bash
uv venv --clear
uv pip install --python .venv --group ../../../pyproject.toml:build
uv pip install --python .venv -e "../../..[dev]"
```

After that, `uv run` syncs the rest automatically.

`--python .venv`: this directory's venv, whatever venv is active - `uv pip` would otherwise install into
an activated one (e.g. py10x's own), while `uv run` / `uv sync` always use this project's `.venv`.

The C++ packages build without isolation, so their toolchain (scikit-build-core, cmake, ninja, ...)
comes first, from py10x's `build` dependency group. Then py10x-core[dev], which builds the kernel:
this extension's build needs an installed kernel, and `uv run` cannot order that on its own.
`py10x-kernel`, `py10x-infra` and this extension build into this directory's `.venv`, so `--clear`
also resets the builds.

## Run

```bash
uv run python test.py
```

