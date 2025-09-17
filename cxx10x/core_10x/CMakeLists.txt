cmake_minimum_required(VERSION 3.27)
project(core_10x_i)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXXFLAGS_DEBUG "-g -O0")

find_package(Python3 REQUIRED COMPONENTS Interpreter Development)

include(FetchContent)
FetchContent_Declare(
        pybind11
        GIT_REPOSITORY https://github.com/pybind/pybind11
        GIT_TAG        v2.13.6
        OVERRIDE_FIND_PACKAGE
)
FetchContent_MakeAvailable(pybind11)

FetchContent_Declare(
        pybind11_stubgen
        GIT_REPOSITORY https://github.com/sizmailov/pybind11-stubgen.git
        GIT_TAG v2.5.5
)
FetchContent_MakeAvailable(pybind11_stubgen)

find_package(pybind11 REQUIRED)

pybind11_add_module(core_10x_i
        bnucleus.cpp
        bnode.cpp
        btrait.cpp
        btrait_processor.cpp
        btraitable.cpp
        btraitable_class.cpp
        btraitable_processor.cpp
        core_10x.cpp
        py_linkage.cpp
        thread_context.cpp
        tid.cpp
        bprocess_context.cpp
        btraitable_ui_extension.cpp
        xcache.cpp
        os_user.cpp
)

target_include_directories(core_10x_i PRIVATE ${stduuid_SOURCE_DIR}/include)


# Generate .pyi stubs after building the module
if(NOT DEFINED CMAKE_LIBRARY_OUTPUT_DIRECTORY)
    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
endif()
# Platform-specific PYTHONPATH separator
if(WIN32)
    set(PYTHONPATH_SEP ";")
else()
    set(PYTHONPATH_SEP ":")
endif()
add_custom_command(
        TARGET core_10x_i POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E env "PYTHONPATH=${pybind11_stubgen_SOURCE_DIR}${PYTHONPATH_SEP}${CMAKE_LIBRARY_OUTPUT_DIRECTORY}" ${Python3_EXECUTABLE} -m pybind11_stubgen core_10x_i -o ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}
        WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
        COMMENT "Generating type stubs for core_10x_i"
        VERBATIM
)

install(TARGETS core_10x_i
        LIBRARY DESTINATION .
        RUNTIME DESTINATION .
)

# Install the generated .pyi alongside the module
install(FILES ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/core_10x_i.pyi DESTINATION .)