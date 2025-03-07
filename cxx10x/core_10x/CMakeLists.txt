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
#FetchContent_Declare(
#        stduuid
#        GIT_REPOSITORY https://github.com/mariusbancila/stduuid
#        GIT_TAG        v1.2.3
#        OVERRIDE_FIND_PACKAGE
#)
FetchContent_MakeAvailable(pybind11)# stduuid)

find_package(pybind11 REQUIRED)
#find_package(stduuid REQUIRED)

pybind11_add_module(core_10x_i
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
        #interactive_processor.cpp
        xcache.cpp
        simple_cache_layer.cpp
)

target_include_directories(core_10x_i PRIVATE ${stduuid_SOURCE_DIR}/include)

install(TARGETS core_10x_i
        LIBRARY DESTINATION .
        RUNTIME DESTINATION .
)