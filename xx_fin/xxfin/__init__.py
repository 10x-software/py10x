import ctypes
import os
import sys

import py10x_kernel

if sys.platform == "win32":
    os.add_dll_directory(os.path.dirname(py10x_kernel.__file__))

# Promote py10x_kernel to RTLD_GLOBAL so its exported symbols (vtables,
# typeinfo) are visible to cxxfin and any other C++ extension modules that
# subclass its types. Also guarantees py10x_kernel is loaded before cxxfin.
ctypes.CDLL(py10x_kernel.__file__, ctypes.RTLD_GLOBAL)
