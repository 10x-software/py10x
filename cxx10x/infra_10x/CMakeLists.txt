cmake_minimum_required(VERSION 3.27)
project(py10x_infra)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXXFLAGS_DEBUG "-g -O0")

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

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
FetchContent_MakeAvailable(pybind11 pybind11_stubgen)
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

set(PY_LINKAGE_SRC "${CMAKE_CURRENT_SOURCE_DIR}/../core_10x/py_linkage.h")
if(EXISTS "${PY_LINKAGE_SRC}")
    set(PY_LINKAGE_DEST "${CMAKE_CURRENT_SOURCE_DIR}/py_linkage.h")
    file(COPY_FILE "${PY_LINKAGE_SRC}" "${PY_LINKAGE_DEST}" RESULT copy_result)
    if(NOT copy_result EQUAL 0)
        message(FATAL_ERROR "Failed to copy ${PY_LINKAGE_SRC} to ${PY_LINKAGE_DEST}: ${copy_result}")
    endif()
endif()

pybind11_add_module(py10x_infra
        #mongo_db_driver.cpp
        mongo_collection_helper.cpp
        py10x_infra.cpp
)

#target_include_directories(py10x_infra PRIVATE
#        ${mongo-cxx-driver_SOURCE_DIR}/mongocxx/include/mongocxx/v_noabi
#        ${mongo-cxx-driver_BINARY_DIR}/mongocxx/lib/mongocxx/v_noabi
#)

# Generate .pyi stubs after building the module
if(WIN32)
    set(PATH_SEP ";")
    set(BINDIR_SUFFIX "/Release")
else()
    set(PATH_SEP ":")
    set(BINDIR_SUFFIX "")
endif()

if(NOT DEFINED CMAKE_LIBRARY_OUTPUT_DIRECTORY)
    #message("CMAKE_CURRENT_BINARY_DIR: ${CMAKE_CURRENT_BINARY_DIR}")
    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}${BINDIR_SUFFIX})
endif()

set(STUBGEN_PYTHONPATH "${pybind11_stubgen_SOURCE_DIR}${PATH_SEP}${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")
#message("STUBGEN_PYTHONPATH: ${STUBGEN_PYTHONPATH}")

add_custom_command(
        TARGET py10x_infra POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E env "PYTHONPATH=${STUBGEN_PYTHONPATH}" ${Python3_EXECUTABLE} -m pybind11_stubgen py10x_infra -o ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}
        WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
        COMMENT "Generating type stubs for py10x_infra"
        VERBATIM
)

install(TARGETS py10x_infra
        LIBRARY DESTINATION .
        RUNTIME DESTINATION .
)

# Install the generated .pyi alongside the module
install(FILES ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/py10x_infra.pyi DESTINATION .)

#target_link_libraries(py10x_infra PRIVATE mongocxx_static)

