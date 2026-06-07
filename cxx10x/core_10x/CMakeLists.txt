cmake_minimum_required(VERSION 3.27...3.30)
project(py10x_kernel)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXXFLAGS_DEBUG "-g -O0")

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

# Declare backward WITHOUT SOURCE_SUBDIR before FetchPybind11Deps so that
# FetchContent_MakeAvailable builds it fully and creates Backward::Backward.
include(FetchContent)
FetchContent_Declare(
        backward
        GIT_REPOSITORY https://github.com/bombela/backward-cpp.git
        GIT_TAG master
        GIT_SHALLOW    TRUE
)

include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/FetchPybind11Deps.cmake)
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/PybindStubs.cmake)

pybind11_add_module(py10x_kernel
        bnucleus.cpp
        bnode.cpp
        btrait.cpp
        btrait_processor.cpp
        btraitable.cpp
        btraitable_class.cpp
        btraitable_processor.cpp
        py10x_kernel.cpp
        py_linkage.cpp
        tid.cpp
        bprocess_context.cpp
        btraitable_ui_extension.cpp
        xcache.cpp
        os_user.cpp
        bcurve.cpp
)

# Export all symbols so that classes exposed via pybind11 (their vtables and
# typeinfo) are visible to other extension modules that subclass them.
# pybind11_add_module sets hidden visibility by default; we override it here.
set_target_properties(py10x_kernel PROPERTIES
        CXX_VISIBILITY_PRESET default
        VISIBILITY_INLINES_HIDDEN OFF
)

target_include_directories(py10x_kernel PRIVATE ${backward_SOURCE_DIR})
target_link_libraries(py10x_kernel PRIVATE Backward::Backward)

target_compile_definitions(py10x_kernel PRIVATE
        VERSION_INFO="${SKBUILD_PROJECT_VERSION_FULL}"
)

finalize_pybind_module(py10x_kernel)

install(TARGETS py10x_kernel
        LIBRARY DESTINATION .
        RUNTIME DESTINATION .
)
