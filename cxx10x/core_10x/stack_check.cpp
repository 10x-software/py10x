#include "stack_check.h"

#include <algorithm>
#include <cstdint>

#include "py_linkage.h"

#ifdef _WIN32
#   include <windows.h>
#   include <intrin.h>
#else
#   include <pthread.h>
#endif

namespace {
    //-- of the current thread; as in CPython 3.14's hardware_stack_limits()
    struct StackBounds {
        std::uintptr_t  low     = 0;    //-- stacks grow down on every supported platform
        std::uintptr_t  margin  = 0;    //-- 0 if the bounds are unknown: the check never fires

        StackBounds() {
            std::uintptr_t high = 0;
#if defined(_WIN32)
            ULONG_PTR l, h;
            GetCurrentThreadStackLimits(&l, &h);
            ULONG guarantee = 0;
            SetThreadStackGuarantee(&guarantee);    //-- 0 only reads it: what is kept for a stack overflow handler
            low     = l + guarantee;
            high    = h;
#elif defined(__APPLE__)
            const auto self = pthread_self();
            high    = reinterpret_cast<std::uintptr_t>(pthread_get_stackaddr_np(self));
            low     = high - pthread_get_stacksize_np(self);
#elif defined(__GLIBC__)    //-- musl reports too small a stack
            pthread_attr_t attr;
            if (pthread_getattr_np(pthread_self(), &attr) == 0) {
                void* addr = nullptr;
                std::size_t size = 0, guard = 0;
                if (pthread_attr_getstack(&attr, &addr, &size) == 0 && pthread_attr_getguardsize(&attr, &guard) == 0) {
                    low     = reinterpret_cast<std::uintptr_t>(addr) + guard;
                    high    = reinterpret_cast<std::uintptr_t>(addr) + size;
                }
                pthread_attr_destroy(&attr);
            }
#endif
            margin = std::min<std::uintptr_t>(256 * 1024, (high - low) / 4);    //-- a small stack must still run getters
        }
    };

    //-- not the address of a local: AddressSanitizer may move those off the stack
    std::uintptr_t stack_pointer() {
#if defined(_MSC_VER)
        return reinterpret_cast<std::uintptr_t>(_AddressOfReturnAddress());
#else
        return reinterpret_cast<std::uintptr_t>(__builtin_frame_address(0));
#endif
    }
}

void check_stack() {
    thread_local const StackBounds bounds;
    if (stack_pointer() - bounds.low < bounds.margin) {     //-- below low (another stack, e.g. a fiber's) it wraps to a large value
        PyErr_SetString(PyExc_RecursionError, "C stack nearly exhausted");
        throw py::error_already_set();
    }
}
