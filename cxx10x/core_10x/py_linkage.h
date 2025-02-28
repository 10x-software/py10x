//
// Created by AMD on 12/17/2024.
//

#pragma once
#include <iostream>
#include <pybind11/pybind11.h>
#include <pybind11/pytypes.h>
#include <pybind11/functional.h>
#include <pybind11/stl.h>

namespace py = pybind11;

using dict_iter = py::detail::dict_iterator;

template<>
struct std::equal_to<py::object> {
    bool operator() (const py::object& a, const py::object& b) const    { return a.equal(b); }
};

template<>
struct std::hash<py::object> {
    std::size_t operator() (py::object const& key) const noexcept   { return py::hash(key); }
};

template<>
struct std::equal_to<py::args> {
    bool operator() (const py::args& a, const py::args& b) const    { return a.equal(b); }
};

template<>
struct std::hash<py::args> {
    std::size_t operator() (const py::args& key) const noexcept   { return py::hash(key); }
};

class BTraitable;
class BTrait;

class PyLinkage {
    py::object          m_xnone;
    py::object          m_rc_true;
    py::object          m_trait_method_error_class;
    py::args            m_choices_args;

    std::streambuf      *m_py_stream_buf = nullptr;
    std::streambuf      *m_std_stream_buf = nullptr;

    void create_choices_args() {
        m_choices_args = py::make_tuple(m_xnone, py::str("__choices"));
    }

public:
    static PyLinkage*   s_py_linkage;

    static void init(py::object xnone, py::object rc_true, py::object trait_method_error_class) {
        assert(!s_py_linkage);
        s_py_linkage = new PyLinkage(xnone, rc_true, trait_method_error_class);
    }

    static py::object XNone() {
        return s_py_linkage->m_xnone;
    }

    static const py::args& choices_args()
    {
        return s_py_linkage->m_choices_args;
    }

    static py::object RC_TRUE() {
        return s_py_linkage->m_rc_true;
    }

    static std::size_t python_id(const py::object& obj) {
        return py::module_::import("builtins").attr("id")(obj).cast<std::size_t>();
    }

    // will throw if class_module.class_name is not importable
    static bool is_instance(const py::object& obj, const char* py_class_module, const char* py_class_name) {
        py::object py_class = py::module_::import(py_class_module).attr(py_class_name);
        return py::isinstance(obj, py_class);
    }

    explicit PyLinkage(py::object xnone, py::object rc_true, py::object trait_mehod_error_class)
    : m_xnone(xnone), m_rc_true(rc_true), m_trait_method_error_class(trait_mehod_error_class)
    {
        create_choices_args();
    }

    ~PyLinkage() {
        if (m_std_stream_buf) {
            std::cout.rdbuf(m_std_stream_buf);
            delete m_py_stream_buf;
        }
    }

    static void clear() {
        delete s_py_linkage;
    }

    static py::object create_trait_method_error(
        BTraitable* obj,
        BTrait* trait,
        const py::object& method_name,
        const py::object* value = nullptr,
        const py::args* args = nullptr,
        const py::error_already_set* other_exc = nullptr
    );

    static void redirect_stdout_to_python();

};

