cmake_minimum_required(VERSION 3.10)
project(10x_i)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)

# Add both subprojects
add_subdirectory(_core_10x)
add_subdirectory(_infra_10x)
