"""
Shared post-build stub generation for pybind11 modules that depend on py10x_kernel.

Promotes py10x_kernel to RTLD_GLOBAL before importing the target module so
that BTraitable (and other exported symbols) are visible in the flat namespace
on macOS/Linux.

Usage (from CMake):
    python generate_stubs.py <module_name> <stubgen_src_dir> <so_dir> <stub_out_dir>

  module_name    : name of the pybind11 module to generate stubs for
  stubgen_src_dir: FetchContent source dir of pybind11_stubgen
  so_dir         : directory containing <module_name>.so
  stub_out_dir   : directory to write the generated .pyi file
"""
import os
import sys
import ctypes

module_name, stubgen_src_dir, so_dir, stub_out_dir = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

sys.path.insert(0, stubgen_src_dir)
sys.path.insert(0, so_dir)

import py10x_kernel
if sys.platform == "win32":
    os.add_dll_directory(os.path.dirname(py10x_kernel.__file__))
ctypes.CDLL(py10x_kernel.__file__, ctypes.RTLD_GLOBAL)

from pybind11_stubgen.__main__ import main  # noqa
sys.argv = ["pybind11_stubgen", module_name, "-o", stub_out_dir]
main()
