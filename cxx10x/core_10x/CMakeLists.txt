cmake_minimum_required(VERSION 3.27...3.30)
project(py10x_core)

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
find_package(pybind11 REQUIRED)

FetchContent_Declare(
        pybind11_stubgen
        GIT_REPOSITORY https://github.com/sizmailov/pybind11-stubgen.git
        GIT_TAG v2.5.5
)
FetchContent_MakeAvailable(pybind11_stubgen)

FetchContent_Declare(
        backward
        GIT_REPOSITORY https://github.com/bombela/backward-cpp.git
        GIT_TAG master
)
FetchContent_MakeAvailable(backward)

pybind11_add_module(py10x_core
        bnucleus.cpp
        bnode.cpp
        btrait.cpp
        btrait_processor.cpp
        btraitable.cpp
        btraitable_class.cpp
        btraitable_processor.cpp
        core_10x.cpp
        py_linkage.cpp
        tid.cpp
        bprocess_context.cpp
        btraitable_ui_extension.cpp
        xcache.cpp
        os_user.cpp
)

target_include_directories(py10x_core PRIVATE ${backward_SOURCE_DIR})


# Generate .pyi stubs after building the module
if(WIN32)
    set(PATH_SEP ";")
    set(BINDIR_SUFFIX "/Release")
else()
    set(PATH_SEP ":")
    set(BINDIR_SUFFIX "")
endif()

if(NOT DEFINED CMAKE_LIBRARY_OUTPUT_DIRECTORY)
	#message("CMAKE_CURRENT_BINARY_DIR: ${CMAKE_CURRENT_BINARY_DIR}")
    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}${BINDIR_SUFFIX})
endif()

set(STUBGEN_PYTHONPATH "${pybind11_stubgen_SOURCE_DIR}${PATH_SEP}${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")
#message("STUBGEN_PYTHONPATH: ${STUBGEN_PYTHONPATH}")

add_custom_command(
        TARGET py10x_core POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E env "PYTHONPATH=${STUBGEN_PYTHONPATH}" ${Python3_EXECUTABLE} -m pybind11_stubgen py10x_core -o ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}
        WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
        COMMENT "Generating type stubs for py10x_core"
        VERBATIM
)

install(TARGETS py10x_core
        LIBRARY DESTINATION .
        RUNTIME DESTINATION .
)

# Install the generated .pyi alongside the module
install(FILES ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/py10x_core.pyi DESTINATION .)
target_link_libraries(py10x_core PRIVATE Backward::Backward)
