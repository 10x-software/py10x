cmake_minimum_required(VERSION 3.10)
project(10x_i)

# Set C++ standard
set(CMAKE_CXX_STANDARD 20)

# Ensure core_10x and infra_10x output to their own cmake-build-debug directories
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/core_10x/cmake-build-debug)
add_subdirectory(core_10x)

set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/infra_10x/cmake-build-debug)
add_subdirectory(infra_10x)