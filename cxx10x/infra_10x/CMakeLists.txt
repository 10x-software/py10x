cmake_minimum_required(VERSION 3.27)
project(py10x_infra)

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
FetchContent_MakeAvailable(pybind11 pybind11_stubgen)
find_package(pybind11 REQUIRED)

include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/PybindStubs.cmake)

set(PY_LINKAGE_SRC "${CMAKE_CURRENT_SOURCE_DIR}/../core_10x/py_linkage.h")
if(EXISTS "${PY_LINKAGE_SRC}")
    set(PY_LINKAGE_DEST "${CMAKE_CURRENT_SOURCE_DIR}/py_linkage.h")
    file(COPY_FILE "${PY_LINKAGE_SRC}" "${PY_LINKAGE_DEST}" RESULT copy_result)
    if(NOT copy_result EQUAL 0)
        message(FATAL_ERROR "Failed to copy ${PY_LINKAGE_SRC} to ${PY_LINKAGE_DEST}: ${copy_result}")
    endif()
endif()

pybind11_add_module(py10x_infra
        mongo_collection_helper.cpp
        py10x_infra.cpp
)

target_compile_definitions(py10x_infra PRIVATE
        VERSION_INFO="${SKBUILD_PROJECT_VERSION_FULL}"
)

option(ENABLE_SANITIZERS "Enable AddressSanitizer and UndefinedBehaviorSanitizer" OFF)

if(ENABLE_SANITIZERS)
    message(STATUS "Sanitizers enabled")
    target_compile_options(py10x_infra PRIVATE
            -fsanitize=address,undefined
            -fno-omit-frame-pointer
            -g
    )
    target_link_options(py10x_infra PRIVATE
            -fsanitize=address,undefined
    )
else()
    add_pybind_stubs(py10x_infra)
endif()

install(TARGETS py10x_infra
        LIBRARY DESTINATION .
        RUNTIME DESTINATION .
)
