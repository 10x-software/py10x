cmake_minimum_required(VERSION 3.25)  # CMakePresets.json version 6
project(10x_i)

# Set C++ standard
set(CMAKE_CXX_STANDARD 20)

# The Python env of CLion's build and run configurations, cxx10x/.venv: py10x-core (editable, so its
# metadata, entry points and pytest plugin are there) and its locked dependencies from the root uv.lock,
# plus the dev extra for the tests - WITHOUT py10x-kernel / py10x-infra, so that their CLion builds (the
# cmake-build-debug dirs below, put on PYTHONPATH by the run configurations) are what gets imported.
# Created if missing and synced exactly on every configure - a no-op when nothing changed - and CLion
# re-configures when uv.lock changes.
set(PY10X_ROOT ${CMAKE_SOURCE_DIR}/..)
set(CLION_VENV ${CMAKE_SOURCE_DIR}/.venv)
# setuptools-scm (py10x-core's editable build in the venv sync, the module versions below) runs a plain `git` from
# PATH, which CLion's Windows configure need not have (Git Bash's PATH is not the system one): put the git
# find_package found first on PATH for every command this configure runs.
find_package(Git REQUIRED)
get_filename_component(_git_dir ${GIT_EXECUTABLE} DIRECTORY)
if(WIN32)
    set(ENV{PATH} "${_git_dir};$ENV{PATH}")
else()
    set(ENV{PATH} "${_git_dir}:$ENV{PATH}")
endif()
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${PY10X_ROOT}/uv.lock)
find_program(UV_EXECUTABLE uv REQUIRED)
set(_clion_venv_requirements ${CMAKE_BINARY_DIR}/clion-venv-requirements.txt)
execute_process(
        COMMAND ${UV_EXECUTABLE} export --quiet --frozen --no-hashes --no-header --no-default-groups --extra dev
                --no-emit-package py10x-kernel --no-emit-package py10x-infra
                --format requirements-txt --output-file ${_clion_venv_requirements}
        WORKING_DIRECTORY ${PY10X_ROOT}
        COMMAND_ERROR_IS_FATAL ANY)
if(NOT EXISTS ${CLION_VENV}/pyvenv.cfg)
    # From the repo root, so uv picks a Python within py10x's requires-python.
    execute_process(COMMAND ${UV_EXECUTABLE} venv ${CLION_VENV} WORKING_DIRECTORY ${PY10X_ROOT} COMMAND_ERROR_IS_FATAL ANY)
endif()
execute_process(
        COMMAND ${UV_EXECUTABLE} pip sync --python ${CLION_VENV} ${_clion_venv_requirements}
        WORKING_DIRECTORY ${PY10X_ROOT}
        COMMAND_ERROR_IS_FATAL ANY)

if(WIN32)
    set(CLION_PYTHON ${CLION_VENV}/Scripts/python.exe)
else()
    set(CLION_PYTHON ${CLION_VENV}/bin/python)
endif()
# One set of run configurations for every OS: they run .venv/Scripts/python (the Windows venv layout; a link
# to bin/python elsewhere) and find CLion's module builds through a .pth file in the venv, not a PYTHONPATH,
# whose separator differs by OS.
if(NOT WIN32)
    file(MAKE_DIRECTORY ${CLION_VENV}/Scripts)
    file(CREATE_LINK ../bin/python ${CLION_VENV}/Scripts/python SYMBOLIC)
endif()
execute_process(
        COMMAND ${CLION_PYTHON} -c "import sysconfig; print(sysconfig.get_path('purelib'))"
        OUTPUT_VARIABLE _clion_site_packages OUTPUT_STRIP_TRAILING_WHITESPACE
        COMMAND_ERROR_IS_FATAL ANY)
file(WRITE ${_clion_site_packages}/py10x_clion_modules.pth
        "${CMAKE_SOURCE_DIR}/core_10x/cmake-build-debug\n${CMAKE_SOURCE_DIR}/infra_10x/cmake-build-debug\n")

# The modules' __version__, as their scikit-build-core builds stamp it (SKBUILD_PROJECT_VERSION_FULL, which
# CLion's build does not set): setuptools-scm with each package's own tag pattern. Computed at configure,
# so CLion re-configures on the next build after a commit or checkout (git's HEAD log changes).
execute_process(
        COMMAND ${GIT_EXECUTABLE} rev-parse --path-format=absolute --git-path logs/HEAD
        WORKING_DIRECTORY ${PY10X_ROOT}
        OUTPUT_VARIABLE _git_head_log OUTPUT_STRIP_TRAILING_WHITESPACE
        COMMAND_ERROR_IS_FATAL ANY)
if(EXISTS ${_git_head_log})
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${_git_head_log})
endif()
function(py10x_scm_version package out_var)
    execute_process(
            COMMAND ${CLION_PYTHON} -m setuptools_scm --config ${CMAKE_SOURCE_DIR}/${package}/pyproject.toml
            OUTPUT_VARIABLE _version OUTPUT_STRIP_TRAILING_WHITESPACE
            COMMAND_ERROR_IS_FATAL ANY)
    set(${out_var} ${_version} PARENT_SCOPE)
endfunction()

# Build against cxx10x/.venv's Python (set here, not in the preset, whose one profile serves every OS).
set(Python_EXECUTABLE ${CLION_PYTHON} CACHE FILEPATH "cxx10x/.venv Python" FORCE)
set(Python3_EXECUTABLE ${CLION_PYTHON} CACHE FILEPATH "cxx10x/.venv Python" FORCE)
set(PYTHON_EXECUTABLE ${CLION_PYTHON})  # For pybind11 or FindPythonInterp

# Ensure core_10x and infra_10x output to their own cmake-build-debug directories
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/core_10x/cmake-build-debug)
py10x_scm_version(core_10x SKBUILD_PROJECT_VERSION_FULL)
add_subdirectory(core_10x)

set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/infra_10x/cmake-build-debug)
py10x_scm_version(infra_10x SKBUILD_PROJECT_VERSION_FULL)
add_subdirectory(infra_10x)

# Both modules: core_10x and infra_10x tests import both, so every run configuration builds this target.
add_custom_target(py10x_modules)
add_dependencies(py10x_modules py10x_kernel py10x_infra)
