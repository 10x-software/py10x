cmake_minimum_required(VERSION 3.27...3.30)
project(py10x_kernel)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXXFLAGS_DEBUG "-g -O0")

include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/versions.cmake)

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

include(FetchContent)
FetchContent_Declare(
        pybind11
        GIT_REPOSITORY https://github.com/pybind/pybind11
        GIT_TAG        ${PYBIND11_VERSION}
        GIT_SHALLOW    TRUE
        OVERRIDE_FIND_PACKAGE
)
FetchContent_Declare(
        pybind11_stubgen
        GIT_REPOSITORY https://github.com/sizmailov/pybind11-stubgen.git
        GIT_TAG        ${PYBIND11_STUBGEN_VERSION}
        GIT_SHALLOW    TRUE
)
FetchContent_Declare(
        backward
        GIT_REPOSITORY https://github.com/bombela/backward-cpp.git
        GIT_TAG master
        GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(pybind11 pybind11_stubgen backward)
find_package(pybind11 REQUIRED)

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

target_include_directories(py10x_kernel PRIVATE ${backward_SOURCE_DIR})
target_link_libraries(py10x_kernel PRIVATE Backward::Backward)

target_compile_definitions(py10x_kernel PRIVATE
        VERSION_INFO="${SKBUILD_PROJECT_VERSION_FULL}"
)

option(ENABLE_SANITIZERS "Enable AddressSanitizer and UndefinedBehaviorSanitizer" OFF)

if(ENABLE_SANITIZERS)
    message(STATUS "Sanitizers enabled")
    target_compile_options(py10x_kernel PRIVATE
            -fsanitize=address,undefined
            -fno-omit-frame-pointer
            -g
    )
    target_link_options(py10x_kernel PRIVATE
            -fsanitize=address,undefined
    )
else()
    add_pybind_stubs(py10x_kernel)
endif()

install(TARGETS py10x_kernel
        LIBRARY DESTINATION .
        RUNTIME DESTINATION .
)
