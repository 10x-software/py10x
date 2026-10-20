cmake_minimum_required(VERSION 3.27...3.30)
project(cross_module_test)

set(CMAKE_CXX_STANDARD 20)

# Find Python
find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

# Include the shared pybind11 helper from the cxx10x tree.
include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/XX_pybind11_add_module.cmake)

# For building inside the cxx10x source tree we point at the parent so that
# the macro's ${cxx10x_core_headers_SOURCE_DIR}/core_10x resolves correctly
# to the core_10x headers dir (matching how FetchContent works in normal use).
set(cxx10x_core_headers_SOURCE_DIR ${CMAKE_CURRENT_LIST_DIR}/../..)

# This will fetch pybind11 etc. consistently with the main build
xx_pybind11_add_module(cross_module_test cross_module_test.cpp)

# For a real package we install the .pyd / .so
install(TARGETS cross_module_test
        LIBRARY DESTINATION .
        RUNTIME DESTINATION .
)
