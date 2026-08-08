cmake_minimum_required(VERSION 3.27...3.30)
project(cxxfin)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_FLAGS_DEBUG "-g -O0")

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

# ---------------------------------------------------------------------------
# Resolve py10x_kernel headers at the exact git commit matching the installed
# binary.  setuptools_scm embeds the hash in the version string as "+gHASH",
# e.g. "0.1.dev42+gabcdef12.d20260601".  For a clean tag release the version
# is plain "1.2.3" and we reconstruct the tag "py10x-kernel-v1.2.3".
# GIT_SHALLOW is intentionally omitted: shallow clones cannot fetch by hash.
# ---------------------------------------------------------------------------
execute_process(
        COMMAND ${Python3_EXECUTABLE} -c "import py10x_kernel; print(py10x_kernel.__version__)"
        OUTPUT_VARIABLE _PY10X_KERNEL_VERSION
        OUTPUT_STRIP_TRAILING_WHITESPACE
        RESULT_VARIABLE _version_rc
)
if(NOT _version_rc EQUAL 0)
    message(FATAL_ERROR "Could not query py10x_kernel.__version__. Is py10x-kernel installed in the active environment?")
endif()

string(REGEX MATCH "g([0-9a-f]+)" _hash_match "${_PY10X_KERNEL_VERSION}")
if(_hash_match)
    string(REGEX REPLACE "g([0-9a-f]+)" "\\1" _PY10X_KERNEL_GIT_TAG "${_hash_match}")
else()
    set(_PY10X_KERNEL_GIT_TAG "py10x-kernel-v${_PY10X_KERNEL_VERSION}")
endif()
message(STATUS "py10x_kernel ${_PY10X_KERNEL_VERSION} -> fetching headers at ${_PY10X_KERNEL_GIT_TAG}")

include(FetchContent)
FetchContent_Declare(
        cxx10x_core_headers
        GIT_REPOSITORY https://github.com/10x-software/cxx10x.git
        GIT_TAG        ${_PY10X_KERNEL_GIT_TAG}
        SOURCE_SUBDIR  _headers_only
)
FetchContent_MakeAvailable(cxx10x_core_headers)

include(${cxx10x_core_headers_SOURCE_DIR}/cmake/XX_pybind11_add_module.cmake)

xx_pybind11_add_module(cxxfin
        cxxfin.cpp
)

install(TARGETS cxxfin
        LIBRARY DESTINATION .
        RUNTIME DESTINATION .
)
