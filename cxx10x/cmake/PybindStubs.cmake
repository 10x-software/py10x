# add_pybind_stubs(TARGET <target>)
# Adds a post-build command to generate .pyi stubs via pybind11_stubgen.
# Requires pybind11_stubgen_SOURCE_DIR to be set (via FetchContent).
# No-op when ENABLE_SANITIZERS is ON (stub generation is skipped in that mode).
function(add_pybind_stubs target)
    if(WIN32)
        set(_path_sep ";")
        set(_bindir_suffix "/Release")
    else()
        set(_path_sep ":")
        set(_bindir_suffix "")
    endif()

    if(NOT DEFINED CMAKE_LIBRARY_OUTPUT_DIRECTORY)
        set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}${_bindir_suffix})
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
