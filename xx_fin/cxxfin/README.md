# py10x-fin-base-cxx (`cxxfin` import)

Native extension for **py10x-fin-base**. Dist name is `py10x-fin-base-cxx`; the import
module remains `cxxfin`. Install **`py10x-fin-base`** (not this package directly).
Built with pybind11 and scikit-build-core.

## Architecture

- `cxxfin.cpp` — pybind11 module source; `PYBIND11_MODULE` name is `cxxfin`
- `generate_stubs.py` — post-build stub generation; promotes `py10x_kernel` to `RTLD_GLOBAL` before importing `cxxfin` so that `BTraitable` typeinfo is visible (macOS flat namespace requirement)
- Headers fetched from `cxx10x` at the exact git commit matching the installed `py10x_kernel` binary (version string contains the hash)

## Subclassing py10x_kernel types

`py10x_kernel` is built with `CXX_VISIBILITY_PRESET default` so its vtables and typeinfo are exported. On import it promotes itself to `RTLD_GLOBAL` via `dladdr` + `dlopen(RTLD_NOW | RTLD_GLOBAL | RTLD_NOLOAD)`, making its symbols visible to subsequently loaded extension modules. `py10x_kernel` must be imported before `cxxfin` — this holds in normal usage since it is always loaded as part of the `py10x-core` import chain.

## Incremental, automatic rebuild

`cxxfin` on is automatically rebuilt on `import cxxfin` whenever the sources changed. 

## Clean rebuild

Needed when changing build structure, e.g. adding source files, editing `CMakeLists.txt`):

```bash
uv pip uninstall py10x-fin-base-cxx
rm -rf .venv/py10x-build/cxxfin
uv sync --reinstall-package py10x-fin-base-cxx
```

- `uv pip uninstall py10x-fin-base-cxx` — removes the editable finder from site-packages, which
  otherwise intercepts `import cxxfin` during stub generation and causes a circular rebuild
  failure
- `rm -rf .venv/py10x-build/cxxfin` — wipes the stale CMake cache
- `uv sync --reinstall-package py10x-fin-base-cxx` — rebuilds and reinstalls from scratch

Normal development (edit C++ source → run) does not require this; the editable rebuild fires
automatically on import.

## Debug build

`cxxfin` builds `Release` by default. For `Debug` build, set the build type via
scikit-build-core's env override and re-run uv sync, for example:

```bash
SKBUILD_CMAKE_BUILD_TYPE=Debug uv sync --reinstall-package py10x-fin-base-cxx
```

The build type is fixed at sync time (baked into the editable install along with the
build-dir), so switching is just another sync — `SKBUILD_CMAKE_BUILD_TYPE=Debug uv sync --reinstall-package py10x-fin-base-cxx`
for Debug, plain `uv sync --reinstall-package py10x-fin-base-cxx` for Release. Because each type has its own
tree under `.venv/py10x-build/cxxfin/<Debug|Release>/`, switching does not rebuild from
scratch.
