include_guard(GLOBAL)

include(${CMAKE_CURRENT_LIST_DIR}/versions.cmake)

# py10x_check_msvc_version()
#
# Ensures py10x-kernel and dependent extension modules are built with the same
# MSVC toolset. No-op on non-Windows platforms.
function(py10x_check_msvc_version)
    if(NOT WIN32)
        return()
    endif()
    if(NOT MSVC)
        message(FATAL_ERROR "py10x requires MSVC on Windows")
    endif()
    if(NOT MSVC_VERSION EQUAL PY10X_REQUIRED_MSVC_VERSION)
        message(FATAL_ERROR "py10x requires MSVC_VERSION=${PY10X_REQUIRED_MSVC_VERSION}")
    endif()
endfunction()
