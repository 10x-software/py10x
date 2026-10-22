cmake_minimum_required(VERSION 3.27...3.30)
project(cxxfin)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_FLAGS_DEBUG "-g -O0")

# CLion's build (no scikit-build-core) uses xx_fin/cxxfin/.venv: py10x-fin-base (editable) and its locked
# dependencies from py10x's root uv.lock, plus the dev extra - WITHOUT py10x-fin-base-cxx, so that CLion's
# own cxxfin build is what gets imported (by its stub generation too). Created if missing and synced
# exactly on every configure - a no-op when nothing changed - and CLion re-configures when uv.lock changes.
if(NOT SKBUILD)
    set(PY10X_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../..)
    set(CLION_VENV ${CMAKE_CURRENT_SOURCE_DIR}/.venv)
    # setuptools-scm / hatch-vcs (the editable builds in the venv sync) run a plain `git` from PATH, which
    # CLion's Windows configure need not have: put the git find_package found first on PATH.
    find_package(Git REQUIRED)
    get_filename_component(_git_dir ${GIT_EXECUTABLE} DIRECTORY)
    if(WIN32)
        set(ENV{PATH} "${_git_dir};$ENV{PATH}")
    else()
        set(ENV{PATH} "${_git_dir}:$ENV{PATH}")
    endif()
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${PY10X_ROOT}/uv.lock)
    find_program(UV_EXECUTABLE uv REQUIRED)
    set(_clion_venv_build_requirements ${CMAKE_BINARY_DIR}/clion-venv-build-requirements.txt)
    set(_clion_venv_requirements ${CMAKE_BINARY_DIR}/clion-venv-requirements.txt)
    execute_process(
            COMMAND ${UV_EXECUTABLE} export --quiet --frozen --no-hashes --no-header --only-group build
                    --format requirements-txt --output-file ${_clion_venv_build_requirements}
            WORKING_DIRECTORY ${PY10X_ROOT}
            COMMAND_ERROR_IS_FATAL ANY)
    execute_process(
            COMMAND ${UV_EXECUTABLE} export --quiet --frozen --no-hashes --no-header --no-default-groups --extra dev
                    --group test --no-emit-package py10x-fin-base-cxx
                    --format requirements-txt --output-file ${_clion_venv_requirements}
            WORKING_DIRECTORY ${PY10X_ROOT}
            COMMAND_ERROR_IS_FATAL ANY)
    if(NOT EXISTS ${CLION_VENV}/pyvenv.cfg)
        # From the repo root, so uv picks a Python within py10x's requires-python.
        execute_process(COMMAND ${UV_EXECUTABLE} venv ${CLION_VENV} WORKING_DIRECTORY ${PY10X_ROOT} COMMAND_ERROR_IS_FATAL ANY)
    endif()
    # The C++ build toolchain first: kernel/infra build without isolation, and uv does not order their
    # builds after it (as in `./xx-build init`).
    execute_process(
            COMMAND ${UV_EXECUTABLE} pip install --quiet --python ${CLION_VENV} -r ${_clion_venv_build_requirements}
            WORKING_DIRECTORY ${PY10X_ROOT}
            COMMAND_ERROR_IS_FATAL ANY)
    execute_process(
            COMMAND ${UV_EXECUTABLE} pip sync --python ${CLION_VENV} ${_clion_venv_requirements}
            WORKING_DIRECTORY ${PY10X_ROOT}
            COMMAND_ERROR_IS_FATAL ANY)
    if(WIN32)
        set(Python3_EXECUTABLE ${CLION_VENV}/Scripts/python.exe)
    else()
        set(Python3_EXECUTABLE ${CLION_VENV}/bin/python)
    endif()
endif()
find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

# ---------------------------------------------------------------------------
# Resolve py10x_kernel headers.
#
# Editable (local) kernel install -> use its source tree directly. Those are the
# headers the installed binary was actually built from, and CMake tracks them as
# real files, so editing btrait.h rebuilds cxxfin -- the same way infra_10x works
# inside cxx10x. This is the only correct source while developing cxx10x: a dirty
# build ("+gHASH.dYYYYMMDD") has no commit whose headers match the binary, and two
# builds off one commit are indistinguishable to the fetch path below.
#
# Otherwise (wheel from an index) fall back to fetching the exact git commit
# matching the installed binary.  setuptools_scm embeds the hash in the version
# string as "+gHASH",
# e.g. "0.1.dev42+gabcdef12.d20260601".  For a clean tag release the version
# is plain "1.2.3" and we reconstruct the tag "py10x-kernel-v1.2.3".
# GIT_SHALLOW is intentionally omitted: shallow clones cannot fetch by hash.
#
# Use importlib.metadata — do NOT `import py10x_kernel` here. Importing the
# extension runs its import-time incremental rebuild, which prints cmake
# progress on stdout and corrupts the captured version (FetchContent then
# tries to checkout a tag like `py10x-kernel-vRunning cmake --build...`).
# ---------------------------------------------------------------------------
# An editable install records its source tree in direct_url.json (PEP 610). url2pathname, not a
# `file://` slice: on Windows the URL is file:///D:/..., and the slice leaves an invalid /D:/... path.
execute_process(
        COMMAND ${Python3_EXECUTABLE} -c "import json,pathlib,urllib.parse,urllib.request,importlib.metadata as m; du=json.loads(m.distribution('py10x-kernel').read_text('direct_url.json') or '{}'); u=du.get('url',''); print(pathlib.Path(urllib.request.url2pathname(urllib.parse.urlparse(u).path)).parent.as_posix() if du.get('dir_info',{}).get('editable') and u.startswith('file://') else '')"
        OUTPUT_VARIABLE _PY10X_KERNEL_LOCAL_SRC
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
)

if(_PY10X_KERNEL_LOCAL_SRC AND EXISTS "${_PY10X_KERNEL_LOCAL_SRC}/core_10x/btrait.h")
    message(STATUS "py10x_kernel is editable -> using local headers at ${_PY10X_KERNEL_LOCAL_SRC}")
    set(cxx10x_core_headers_SOURCE_DIR "${_PY10X_KERNEL_LOCAL_SRC}")
else()
    execute_process(
            COMMAND ${Python3_EXECUTABLE} -c "import importlib.metadata as m; print(m.version('py10x-kernel'))"
            OUTPUT_VARIABLE _PY10X_KERNEL_VERSION
            OUTPUT_STRIP_TRAILING_WHITESPACE
            ERROR_VARIABLE _version_err
            RESULT_VARIABLE _version_rc
    )
    if(NOT _version_rc EQUAL 0)
        message(FATAL_ERROR "Could not query py10x-kernel version (${_version_err}). Is it installed in the active environment?")
    endif()

    string(REGEX MATCH "g([0-9a-f]+)" _hash_match "${_PY10X_KERNEL_VERSION}")
    if(_hash_match)
        string(REGEX REPLACE "g([0-9a-f]+)" "\\1" _PY10X_KERNEL_GIT_TAG "${_hash_match}")
    else()
        # PEP 440 normalizes bare `.dev` tags to `.dev0`; xx-promote git tags keep `.dev`.
        set(_PY10X_KERNEL_GIT_TAG "py10x-kernel-v${_PY10X_KERNEL_VERSION}")
        string(REGEX REPLACE "\\.dev0$" ".dev" _PY10X_KERNEL_GIT_TAG "${_PY10X_KERNEL_GIT_TAG}")
    endif()
    message(STATUS "py10x_kernel ${_PY10X_KERNEL_VERSION} -> fetching headers at ${_PY10X_KERNEL_GIT_TAG}")

    include(FetchContent)
    FetchContent_Declare(
            cxx10x_core_headers
            GIT_REPOSITORY https://github.com/10x-software/py10x.git
            GIT_TAG        ${_PY10X_KERNEL_GIT_TAG}
            SOURCE_SUBDIR  _headers_only
    )
    FetchContent_MakeAvailable(cxx10x_core_headers)
    # The C++ tree lives under cxx10x/ in the py10x repo; the editable branch above already
    # resolves to that dir (parent of cxx10x/core_10x).
    set(cxx10x_core_headers_SOURCE_DIR "${cxx10x_core_headers_SOURCE_DIR}/cxx10x")
endif()

include(${cxx10x_core_headers_SOURCE_DIR}/cmake/XX_pybind11_add_module.cmake)

xx_pybind11_add_module(cxxfin
        cxxfin.cpp
)

install(TARGETS cxxfin
        LIBRARY DESTINATION .
        RUNTIME DESTINATION .
)
