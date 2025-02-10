cmake_minimum_required(VERSION 3.10)
project(10x_i)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)

# Ensure _core_10x and _infra_10x output to their own cmake-build-debug directories
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/_core_10x/cmake-build-debug)
add_subdirectory(_core_10x)

set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/_infra_10x/cmake-build-debug)
add_subdirectory(_infra_10x)