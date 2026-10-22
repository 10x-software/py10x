# 10x Platform C++ packages

The compiled packages `py10x-core` depends on. They live in the py10x repo but are separate PyPI
packages with their own versions, tags and publish workflow (`.github/workflows/cxx10x_wheels.yml`);
see [`dev_10x/README.md`](../dev_10x/README.md) for releases and dev setup.

- [py10x-kernel](core_10x/README.md) (`core_10x/`)
- [py10x-infra](infra_10x/README.md) (`infra_10x/`)

`CMakeLists.txt` at this level is an IDE-only wrapper (CLion); the package builds use each
package's own `pyproject.toml` / `CMakeLists.txt` plus the shared `cmake/` dir.

## CLion

Open `cxx10x/` as the CLion project; everything it needs is shared through git:

- `CMakePresets.json`: the `Debug` profile (CLion loads presets disabled - enable it once under
  Settings > Build, Execution, Deployment > CMake). On Windows it selects CLion's `Visual Studio`
  toolchain at MSVC 14.44, the toolset py10x requires.
- `CMakeLists.txt` creates and syncs `cxx10x/.venv` on every configure (needs `uv` on PATH): py10x-core
  (editable) and its locked dependencies from the root `uv.lock` plus its `dev` extra, but not
  py10x-kernel / py10x-infra, so the run configurations import CLion's own builds (`core_10x/` and
  `infra_10x/cmake-build-debug`, on their `PYTHONPATH`).
- `.idea/runConfigurations/`: run `core_10x/tests/test.py` / `infra_10x/tests/test.py` with that venv.

## Test harnesses

Minimal uv harness directories under `tests/` (run the real core tests with editable builds of the
C++ packages and of py10x-core at the repo root; CI job `cxx10x-tests`):

- `py10x_kernel_test/` – for kernel testing. See `tests/py10x_kernel_test/README.md`
- `py10x_infra_test/` – for infra testing. See `tests/py10x_infra_test/README.md`
- `cross_module_test/` – for cross-module pybind11 (s_cxx_mixins etc.). See `tests/cross_module_test/README.md`
