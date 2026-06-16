# 10x Platform dependencies

- [py10x_kernel](https://github.com/10x-software/cxx10x/blob/main/core_10x/README.md)
- [py10x_infra](https://github.com/10x-software/cxx10x/blob/main/infra_10x/README.md)

## Test harnesses

Minimal uv harness directories under `tests/` (for running the real core tests with editable builds from sibling py10x checkout):

- `py10x_kernel_test/` – for kernel testing. See `tests/py10x_kernel_test/README.md`
- `py10x_infra_test/` – for infra testing. See `tests/py10x_infra_test/README.md`
- `cross_module_test/` – for cross-module pybind11 (s_cxx_mixins etc.). See `tests/cross_module_test/README.md`
