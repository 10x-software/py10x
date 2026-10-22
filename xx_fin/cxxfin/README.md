# py10x-fin-base-cxx (`cxxfin` import)

Native extension for **py10x-fin-base**. Dist name is `py10x-fin-base-cxx`; the import
module remains `cxxfin`. Install **`py10x-fin-base`** (not this package directly).
Built with pybind11 and scikit-build-core.

## Architecture

- `cxxfin.cpp` — pybind11 module source; `PYBIND11_MODULE` name is `cxxfin`
- `generate_stubs.py` — post-build stub generation; promotes `py10x_kernel` to `RTLD_GLOBAL` before importing `cxxfin` so that `BTraitable` typeinfo is visible (macOS flat namespace requirement)
- Headers from the py10x repo's `cxx10x/` at the exact git commit matching the installed `py10x_kernel` binary (version string contains the hash), or the local tree when `py10x-kernel` is installed editable

## Subclassing py10x_kernel types

`py10x_kernel` is built with `CXX_VISIBILITY_PRESET default` so its vtables and typeinfo are exported. On import it promotes itself to `RTLD_GLOBAL` via `dladdr` + `dlopen(RTLD_NOW | RTLD_GLOBAL | RTLD_NOLOAD)`, making its symbols visible to subsequently loaded extension modules. `py10x_kernel` must be imported before `cxxfin` — this holds in normal usage since it is always loaded as part of the `py10x-core` import chain.

## Incremental, automatic rebuild

`cxxfin` follows uv-sync's `XX_UV_INSTALL_MODE`, like `py10x-kernel` / `py10x-infra`. In the
default `incremental_quiet` mode (and `incremental`), it is installed editable with a persistent
build dir under `build/py10x-build/cxxfin/<Debug|Release>/` and is automatically rebuilt on
`import cxxfin` whenever the sources changed. In `editable` mode (what CI uses) it is a plain
editable install with no rebuild-on-import check; `normal` installs it non-editable. See
`dev_10x/README.md` for the modes.

## Clean rebuild

Needed when changing build structure, e.g. adding source files, editing `CMakeLists.txt`):

```bash
uv pip uninstall py10x-fin-base-cxx
rm -rf build/py10x-build/cxxfin
uv run --no-sync python -m dev_10x.uv_sync py10x-dev --all-extras --with-downstream
```

- `uv pip uninstall py10x-fin-base-cxx` — removes the editable finder from site-packages, which
  otherwise intercepts `import cxxfin` during stub generation and causes a circular rebuild
  failure
- `rm -rf build/py10x-build/cxxfin` — wipes the stale CMake cache
- the uv-sync re-run rebuilds and reinstalls from scratch

Normal development (edit C++ source → run) does not require this; the editable rebuild fires
automatically on import.

## CLion

Open `xx_fin/cxxfin/` as the CLion project; everything it needs is shared through git:

- `CMakePresets.json`: a Windows-only `Debug` preset, selecting CLion's `Visual Studio` toolchain at
  MSVC 14.44. Elsewhere it does not exist (a `condition`), and CLion uses its own default profile, also
  named `Debug` - nothing to set up. On Windows, once: on first open CLion creates that default `Debug`
  profile too (default toolchain, whose configure fails), which hides the preset of the same name. Under
  Settings > Build, Execution, Deployment > CMake, delete that profile, enable the `Debug` preset, then
  Tools > CMake > Reset Cache and Reload Project.
- `CMakeLists.txt` creates and syncs `xx_fin/cxxfin/.venv` on every CLion configure (needs `uv` on
  PATH): py10x-fin-base (editable) and its locked dependencies from py10x's root `uv.lock` plus the `dev`
  extra, but not py10x-fin-base-cxx, so CLion's own `cxxfin` build is the one its stub generation
  imports. py10x-kernel / py10x-infra are built there editable, sharing their build dir with the root
  `.venv`. Package builds (scikit-build-core) skip all of this.

## Build type

`cxxfin` builds `Debug` by default for development (`cmake.build-type` in its `pyproject.toml`).
For a `Release` build, set scikit-build-core's build-type env var and re-run uv-sync (or a plain
`uv pip install -e`):

```bash
SKBUILD_CMAKE_BUILD_TYPE=Release uv run --no-sync python -m dev_10x.uv_sync py10x-dev --all-extras --with-downstream
```

The build type is fixed at sync time (baked into the editable install along with the build dir),
so switching is just another sync. Because each type has its own tree under
`build/py10x-build/cxxfin/<Debug|Release>/`, switching does not rebuild from scratch.
