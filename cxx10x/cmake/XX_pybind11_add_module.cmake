include_guard(GLOBAL)

include(${CMAKE_CURRENT_LIST_DIR}/FetchPybind11Deps.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/PybindStubs.cmake)

# xx_pybind11_add_module(<target> <source>...)
#
# Convenience macro for pybind11 extension modules in the xx ecosystem that
# depend on py10x_kernel types. Handles:
#   - fetching pybind11, pybind11_stubgen, backward (via FetchPybind11Deps)
#   - adding include dirs for core_10x headers and backward
#   - setting VERSION_INFO from scikit-build-core
#   - RTLD link options (-undefined dynamic_lookup / --allow-shlib-undefined)
#   - sanitizer or stub generation (via finalize_pybind_module_rtld)
#
# Requires cxx10x_core_headers_SOURCE_DIR to be set (via FetchContent) before
# calling this macro. Install rules are left to the caller.
macro(xx_pybind11_add_module target)
    pybind11_add_module(${target} ${ARGN})

    target_include_directories(${target} PRIVATE
            ${cxx10x_core_headers_SOURCE_DIR}/core_10x
            ${backward_SOURCE_DIR}
    )

    target_compile_definitions(${target} PRIVATE
            VERSION_INFO="${SKBUILD_PROJECT_VERSION_FULL}"
    )

    finalize_pybind_module_rtld(${target} ${cxx10x_core_headers_SOURCE_DIR}/cmake)
endmacro()
