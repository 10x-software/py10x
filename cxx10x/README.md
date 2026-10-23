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

- `CMakePresets.json`: a Windows-only `Debug` preset, selecting CLion's `Visual Studio` toolchain at
  MSVC 14.44, the toolset py10x requires. Elsewhere it does not exist (a `condition`), and CLion uses its
  own default profile, also named `Debug` - nothing to set up. On Windows, once: on first open CLion
  creates that default `Debug` profile too (default toolchain, whose configure fails), which hides the
  preset of the same name. Under Settings > Build, Execution, Deployment > CMake, delete that profile,
  enable the `Debug` preset, then Tools > CMake > Reset Cache and Reload Project.
- `CMakeLists.txt` creates and syncs `cxx10x/.venv` on every configure (needs `uv` on PATH): py10x-core
  (editable) and its locked dependencies from the root `uv.lock` plus its `dev` extra, but not
  py10x-kernel / py10x-infra, so the run configurations import CLion's own builds (`core_10x/` and
  `infra_10x/cmake-build-debug`, through a `.pth` file it writes into the venv).
- `.idea/runConfigurations/`: build both modules, then run `core_10x/tests/test.py` /
  `infra_10x/tests/test.py` with that venv, one set for every OS: they run `.venv/Scripts/python`, which
  `CMakeLists.txt` links to `bin/python` outside Windows.

On Windows, CLion's configure need not have git on PATH, but setuptools-scm runs a plain `git` (without one it fails
with `ERROR: no version found for`), so the configure puts the git CMake's `FindGit` finds first on PATH. Git must be
on the PATH CLion sees or where `FindGit` looks on its own: `Git\cmd` or `Git\bin` under `C:\Program Files` or
`C:\Program Files (x86)` (Git for Windows' default; its per-user `%LOCALAPPDATA%\Programs\Git` is not searched),
`%LOCALAPPDATA%\GitHub\PortableGit*`, or SourceTree's `%LOCALAPPDATA%\Atlassian\SourceTree\git_local\bin`. Otherwise
set `-DGIT_EXECUTABLE=<path to git.exe>` in CLion's CMake options; without any of these the configure stops with
`Could NOT find Git`. See [INSTALLATION.md](../INSTALLATION.md#windows).

## Test harnesses

Minimal uv harness directories under `tests/` (run the real core tests with editable builds of the
C++ packages and of py10x-core at the repo root; CI job `cxx10x-tests`):

- `py10x_kernel_test/` – for kernel testing. See `tests/py10x_kernel_test/README.md`
- `py10x_infra_test/` – for infra testing. See `tests/py10x_infra_test/README.md`
- `cross_module_test/` – for cross-module pybind11 (s_cxx_mixins etc.). See `tests/cross_module_test/README.md`
