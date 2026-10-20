#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "btraitable.h"   // pulled in via the headers from cxx10x core_10x

namespace py = pybind11;

// Minimal "mixin" class, exactly like BSampleTraitable in cxxfin
class BCrossTestMixin {
public:
    // This is the key: direct BTraitable* parameter in a pybind11-exposed method.
    // With matching builds (same pybind11 + same compiler invocation via shared CMake),
    // the internals registry is shared, so the caster from the kernel is visible here.
    static py::object test_get(BTraitable* self) {
        if (!self) {
            return py::none();
        }
        // Exercise using the pointer: call a method on it and return something.
        // id_value() is simple and always available.
        py::object idv = self->id_value();
        return py::str("cross_ok:") + idv;
    }
};

// Also a free function for direct testing of the type in a signature.
py::object free_accept(BTraitable* obj) {
    if (!obj) return py::str("null");
    return py::str("free:") + obj->id_value();
}

PYBIND11_MODULE(cross_module_test, m)
{
    // Must import the kernel first so its types are registered in the shared (or visible) pybind11 internals.
    py::module_::import("py10x_kernel");

    m.doc() = "Cross-module pybind11 test package (mimics cxxfin usage of py10x-kernel types)";

    py::class_<BCrossTestMixin>(m, "BCrossTestMixin")
        .def("test_get", &BCrossTestMixin::test_get);

    m.def("free_accept", &free_accept, "Accepts a BTraitable* directly to verify cross-module caster.");
}
