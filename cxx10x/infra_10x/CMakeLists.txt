cmake_minimum_required(VERSION 3.27)
project(py10x_infra)

set(CMAKE_CXX_STANDARD 20)
if(MSVC)
    set(CMAKE_CXX_FLAGS_DEBUG "/Zi /Od")
else()
    set(CMAKE_CXX_FLAGS_DEBUG "-g -O0")
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/FetchPybind11Deps.cmake)
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

finalize_pybind_module(py10x_infra)

install(TARGETS py10x_infra
        LIBRARY DESTINATION .
        RUNTIME DESTINATION .
)
