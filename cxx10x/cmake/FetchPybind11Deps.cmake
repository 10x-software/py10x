include(${CMAKE_CURRENT_LIST_DIR}/versions.cmake)

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
        SOURCE_SUBDIR  _headers_only
)
FetchContent_MakeAvailable(pybind11 pybind11_stubgen backward)
find_package(pybind11 REQUIRED)
