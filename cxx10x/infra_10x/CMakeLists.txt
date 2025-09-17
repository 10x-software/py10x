cmake_minimum_required(VERSION 3.27)
project(infra_10x_i)

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
FetchContent_Declare(
        pybind11_stubgen
        GIT_REPOSITORY https://github.com/sizmailov/pybind11-stubgen.git
        GIT_TAG v2.5.5
)
FetchContent_MakeAvailable(pybind11_stubgen)
#FetchContent_Declare(
#        mongo-cxx-driver
#        GIT_REPOSITORY https://github.com/mongodb/mongo-cxx-driver
#        GIT_TAG        r4.0.0
#        OVERRIDE_FIND_PACKAGE
#)
#set(BUILD_SHARED_LIBS OFF CACHE BOOL "Build mongo-cxx-driver as a static library" FORCE)
#FetchContent_MakeAvailable(pybind11 mongo-cxx-driver)

find_package(pybind11 REQUIRED)
#find_package(mongo-cxx-driver REQUIRED)

pybind11_add_module(infra_10x_i
        #mongo_db_driver.cpp
        mongo_collection_helper.cpp
        infra_10x_i.cpp
)

#target_include_directories(infra_10x_i PRIVATE
#        ${mongo-cxx-driver_SOURCE_DIR}/mongocxx/include/mongocxx/v_noabi
#        ${mongo-cxx-driver_BINARY_DIR}/mongocxx/lib/mongocxx/v_noabi
#)

# Generate .pyi stubs after building the module
if(NOT DEFINED CMAKE_LIBRARY_OUTPUT_DIRECTORY)
    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
endif()
# Platform-specific PYTHONPATH separator
if(WIN32)
    set(PYTHONPATH_SEP ";")
else()
    set(PYTHONPATH_SEP ":")
endif()
add_custom_command(
        TARGET infra_10x_i POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E env "PYTHONPATH=${pybind11_stubgen_SOURCE_DIR}${PYTHONPATH_SEP}${CMAKE_LIBRARY_OUTPUT_DIRECTORY}" ${Python3_EXECUTABLE} -m pybind11_stubgen infra_10x_i -o ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}
        WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
        COMMENT "Generating type stubs for infra_10x_i"
        VERBATIM
)

install(TARGETS infra_10x_i
        LIBRARY DESTINATION .
        RUNTIME DESTINATION .
)

# Install the generated .pyi alongside the module
install(FILES ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/infra_10x_i.pyi DESTINATION .)

#target_link_libraries(infra_10x_i PRIVATE mongocxx_static)

