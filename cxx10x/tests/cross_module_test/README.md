# cross_module_test

This is a small self-contained test package (separate `pyproject.toml` + scikit-build-core + the shared `cmake/XX_pybind11_add_module.cmake`).

It demonstrates using py10x-kernel types (including BTraitable*) from another extension: C++ getters via s_cxx_mixins and direct calls to C++ methods. It works when the kernel and extension share the same build configuration (identical PYBIND11_INTERNALS_ID).

The s_cxx_mixins demonstration is in `test.py` (function `test_with_s_cxx_mixins`).

This is the canonical test for the PY10X_API + shared-build cross-module story.

## First-time / fresh-start preparation (run once)

```bash
uv venv --clear
uv pip install -e "../../..[dev]"
```

After that, `uv run` syncs the rest automatically.

The C++ packages build without isolation, so their toolchain (scikit-build-core, cmake, ninja, ...)
comes first, from `py10x-core[dev]`. `py10x-kernel`, `py10x-infra` and this extension build into this directory's
`.venv`, so `--clear` also resets the builds.

## Run

```bash
uv run python test.py
```

