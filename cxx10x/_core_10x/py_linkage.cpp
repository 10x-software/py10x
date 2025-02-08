//
// Created by AMD on 12/17/2024.
//

#include <cstdio>
#include <iostream>

#include "py_linkage.h"
#include "btraitable.h"

PyLinkage* PyLinkage::s_py_linkage = nullptr;

py::object PyLinkage::create_trait_method_error(
        BTraitable* obj,
        BTrait* trait,
        const py::object& method_name,
        const py::object* value,
        const py::args* args,
        const py::error_already_set* other_exc
) {
    auto create = s_py_linkage->m_trait_method_error_class.attr("create");
    auto py_value = value ? *value : s_py_linkage->m_xnone;
    auto py_args = args? *args : py::args();
    auto py_other_exc = other_exc ? other_exc->value() : py::none();

    return create(obj, trait, method_name, py_value, py_args, py_other_exc);
}

void PyLinkage::redirect_stdout_to_python() {
    py::module sys = py::module::import("sys");
    py::object py_stdout = sys.attr("stdout");

    auto write = py_stdout.attr("write");
    auto flush = py_stdout.attr("flush");

    class PyStreamBuffer : public std::streambuf {
        decltype(write) m_write;
        decltype(flush) m_flush;
    protected:
        int overflow(int c) override {
            if (c != EOF) {
                char ch = (char)c;
                m_write(py::str(std::string(1, ch)));
            }
            return c;
        }
        int sync() override {
            m_flush();
            return 0;
        }

    public:
        PyStreamBuffer(decltype(write) write_func, decltype(flush) flush_func)
        : m_write(write_func), m_flush(flush_func) {}
    };

    static PyStreamBuffer py_buf(write, flush);
    std::cout.rdbuf(&py_buf);

}
