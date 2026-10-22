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

# The modules' __version__, as their scikit-build-core builds stamp it (SKBUILD_PROJECT_VERSION_FULL, which
# CLion's build does not set): setuptools-scm with each package's own tag pattern. Computed at configure,
# so CLion re-configures on the next build after a commit or checkout (git's HEAD log changes).
if(WIN32)
    set(CLION_PYTHON ${CLION_VENV}/Scripts/python.exe)
else()
    set(CLION_PYTHON ${CLION_VENV}/bin/python)
endif()
find_package(Git REQUIRED)
execute_process(
        COMMAND ${GIT_EXECUTABLE} rev-parse --path-format=absolute --git-path logs/HEAD
        WORKING_DIRECTORY ${PY10X_ROOT}
        OUTPUT_VARIABLE _git_head_log OUTPUT_STRIP_TRAILING_WHITESPACE
        COMMAND_ERROR_IS_FATAL ANY)
if(EXISTS ${_git_head_log})
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${_git_head_log})
endif()
# setuptools-scm runs a plain `git` from PATH, which CLion's Windows configure need not have (Git Bash's PATH is not
# the system one): put the git find_package found first on its PATH.
get_filename_component(_git_dir ${GIT_EXECUTABLE} DIRECTORY)
function(py10x_scm_version package out_var)
    execute_process(
            COMMAND ${CMAKE_COMMAND} -E env --modify PATH=path_list_prepend:${_git_dir}
                    ${CLION_PYTHON} -m setuptools_scm --config ${CMAKE_SOURCE_DIR}/${package}/pyproject.toml
            OUTPUT_VARIABLE _version OUTPUT_STRIP_TRAILING_WHITESPACE
            COMMAND_ERROR_IS_FATAL ANY)
    set(${out_var} ${_version} PARENT_SCOPE)
endfunction()

# Map CLion's Python_EXECUTABLE to standard variables
if(DEFINED Python_EXECUTABLE)
    message("Python_EXECUTABLE from CLion: ${Python_EXECUTABLE}")
    set(PYTHON_EXECUTABLE "${Python_EXECUTABLE}")  # For pybind11 or FindPythonInterp
endif()

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
