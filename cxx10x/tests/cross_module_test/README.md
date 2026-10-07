# cross_module_test

This is a small self-contained test package (separate `pyproject.toml` + scikit-build-core + the shared `cmake/XX_pybind11_add_module.cmake`).

It demonstrates using py10x-kernel types (including BTraitable*) from another extension: C++ getters via s_cxx_mixins and direct calls to C++ methods. It works when the kernel and extension share the same build configuration (identical PYBIND11_INTERNALS_ID).

The s_cxx_mixins demonstration is in `test.py` (function `test_with_s_cxx_mixins`).

This is the canonical test for the PY10X_API + shared-build cross-module story.

## Initial setup (clean state)

Run this when you want a completely fresh start:

```bash
rm -rf .venv build uv.lock
uv venv
uv pip install -r pyproject.toml 
```

## Run

```bash
uv run python test.py
```

