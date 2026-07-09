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

    # On Windows, link against py10x_kernel's import library (.lib) so the MSVC
    # linker can resolve symbols like BTraitable that are dllimport-annotated.
    # The .lib is installed alongside py10x_kernel.pyd by core_10x/CMakeLists.txt.
    # On Linux/macOS, consumer extensions rely on py10x_kernel being promoted to
    # RTLD_GLOBAL before load (see core_10x/__init__.py and generate_stubs.py).
    if(WIN32)
        execute_process(
                COMMAND ${Python3_EXECUTABLE} -c "import py10x_kernel,sys; sys.stdout.write('<<<MOD:'+py10x_kernel.__file__+':MOD>>>')"
                OUTPUT_VARIABLE _PY10X_KERNEL_OUT
                RESULT_VARIABLE _mod_rc
        )
        if(NOT _mod_rc EQUAL 0)
            message(FATAL_ERROR "Could not locate py10x_kernel.__file__. Is py10x-kernel installed?")
        endif()
        if(NOT _PY10X_KERNEL_OUT MATCHES "<<<MOD:(.+):MOD>>>")
            message(FATAL_ERROR "Could not parse py10x_kernel.__file__ from output:\n${_PY10X_KERNEL_OUT}")
        endif()
        set(_PY10X_KERNEL_MODULE "${CMAKE_MATCH_1}")

        set(_PY10X_KERNEL_PYD "${_PY10X_KERNEL_MODULE}")
        # MSVC names the import library after the CMake target name (py10x_kernel),
        # NOT the module's full output name. So the file is py10x_kernel.lib, sitting
        # next to py10x_kernel.cp312-win_amd64.pyd. Strip the full extension chain
        # (.cp312-win_amd64.pyd) down to the base module name, then append .lib.
        get_filename_component(_pyd_dir "${_PY10X_KERNEL_PYD}" DIRECTORY)
        get_filename_component(_pyd_name "${_PY10X_KERNEL_PYD}" NAME)
        string(REGEX REPLACE "\\..*$" "" _kernel_base "${_pyd_name}")  # py10x_kernel
        set(_PY10X_KERNEL_LIB "${_pyd_dir}/${_kernel_base}.lib")
        if(NOT EXISTS "${_PY10X_KERNEL_LIB}")
            message(FATAL_ERROR
                "py10x_kernel import library not found at ${_PY10X_KERNEL_LIB}.\n"
                "Rebuild and reinstall py10x-kernel to generate the .lib.")
        endif()
        add_library(py10x_kernel_import SHARED IMPORTED)
        set_target_properties(py10x_kernel_import PROPERTIES
                IMPORTED_IMPLIB "${_PY10X_KERNEL_LIB}"
        )
        target_link_libraries(${target} PRIVATE py10x_kernel_import)
    endif()

    finalize_pybind_module_rtld(${target} ${cxx10x_core_headers_SOURCE_DIR}/cmake)
endmacro()
