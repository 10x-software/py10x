option(ENABLE_SANITIZERS "Enable AddressSanitizer and UndefinedBehaviorSanitizer" OFF)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

function(_resolve_lib_output_dir)
    if(NOT DEFINED CMAKE_LIBRARY_OUTPUT_DIRECTORY)
        if(WIN32)
            set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/Release PARENT_SCOPE)
        else()
            set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR} PARENT_SCOPE)
        endif()
    endif()
endfunction()

# Install the MSVC import library (.lib) generated for an exporting module
# (ENABLE_EXPORTS ON). Mirrors how the .pyi is installed: uses the resolved
# library output dir and a standard install() command so scikit-build-core
# tracks and packages it. Modules that export nothing (e.g. cxxfin) simply have
# no matching .lib and nothing is installed.
function(_install_import_lib target)
    if(NOT MSVC)
        return()
    endif()
    _resolve_lib_output_dir()
    install(DIRECTORY "${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/"
            DESTINATION .
            FILES_MATCHING PATTERN "${target}*.lib")
endfunction()

function(_add_rtld_link_options target)
    if(APPLE)
        target_link_options(${target} PRIVATE -undefined dynamic_lookup)
    elseif(UNIX)
        target_link_options(${target} PRIVATE -Wl,--allow-shlib-undefined)
    endif()
endfunction()

function(_add_sanitizers target)
    message(STATUS "Sanitizers enabled for ${target}")
    target_compile_options(${target} PRIVATE
            -fsanitize=address,undefined
            -fno-omit-frame-pointer
            -g
    )
    target_link_options(${target} PRIVATE
            -fsanitize=address,undefined
    )
endfunction()

# ---------------------------------------------------------------------------
# add_pybind_stubs(target)
# Post-build stub generation for self-contained pybind11 modules.
# ---------------------------------------------------------------------------
function(add_pybind_stubs target)
    _resolve_lib_output_dir()

    if(WIN32)
        set(_path_sep ";")
    else()
        set(_path_sep ":")
    endif()
    set(_stubgen_pythonpath "${pybind11_stubgen_SOURCE_DIR}${_path_sep}${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")

    add_custom_command(
            TARGET ${target} POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E env "PYTHONPATH=${_stubgen_pythonpath}"
                    ${Python3_EXECUTABLE} -m pybind11_stubgen ${target} -o ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}
            WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
            COMMENT "Generating type stubs for ${target}"
            VERBATIM
    )
    install(FILES ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/${target}.pyi DESTINATION .)
endfunction()

# ---------------------------------------------------------------------------
# add_pybind_stubs_rtld(target cxx10x_cmake_dir)
# Post-build stub generation for modules that subclass py10x_kernel types.
# Uses generate_stubs.py which promotes py10x_kernel to RTLD_GLOBAL first.
# ---------------------------------------------------------------------------
function(add_pybind_stubs_rtld target cxx10x_cmake_dir)
    _resolve_lib_output_dir()

    add_custom_command(
            TARGET ${target} POST_BUILD
            COMMAND ${Python3_EXECUTABLE} ${cxx10x_cmake_dir}/generate_stubs.py
                    ${target}
                    ${pybind11_stubgen_SOURCE_DIR}
                    ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}
                    ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}
            WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
            COMMENT "Generating type stubs for ${target} (RTLD)"
            VERBATIM
    )
    install(FILES ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/${target}.pyi DESTINATION .)
endfunction()

# ---------------------------------------------------------------------------
# finalize_pybind_module(target)
# Applies sanitizers or stub generation depending on ENABLE_SANITIZERS.
# For self-contained modules (core_10x, infra_10x style).
# ---------------------------------------------------------------------------
function(finalize_pybind_module target)
    if(ENABLE_SANITIZERS)
        _add_sanitizers(${target})
    else()
        add_pybind_stubs(${target})
    endif()
    _install_import_lib(${target})
endfunction()

# ---------------------------------------------------------------------------
# finalize_pybind_module_rtld(target cxx10x_cmake_dir)
# As above, but uses RTLD-aware stub generation for consumer packages
# that subclass py10x_kernel types (e.g. cxxfin).
# ---------------------------------------------------------------------------
function(finalize_pybind_module_rtld target cxx10x_cmake_dir)
    _add_rtld_link_options(${target})
    if(ENABLE_SANITIZERS)
        _add_sanitizers(${target})
    else()
        add_pybind_stubs_rtld(${target} ${cxx10x_cmake_dir})
    endif()
endfunction()
