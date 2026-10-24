include(${CMAKE_CURRENT_LIST_DIR}/versions.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/Py10xMsvcVersion.cmake)

include(FetchContent)
FetchContent_Declare(
        pybind11
        GIT_REPOSITORY https://github.com/pybind/pybind11
        GIT_TAG        ${PYBIND11_VERSION}
        GIT_SHALLOW    TRUE
        OVERRIDE_FIND_PACKAGE
)
FetchContent_Declare(
        backward
        GIT_REPOSITORY https://github.com/bombela/backward-cpp.git
        GIT_TAG master
        GIT_SHALLOW    TRUE
        SOURCE_SUBDIR  _headers_only
)
# pybind11-stubgen is a Python build dependency (build-system.requires), not fetched: its repo's test
# tree is too deep for Windows' MAX_PATH under a build dir.
FetchContent_MakeAvailable(pybind11 backward)
find_package(pybind11 REQUIRED)

py10x_check_msvc_version()
