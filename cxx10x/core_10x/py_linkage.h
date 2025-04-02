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
    //-- builtins
    py::object          m_type_cls;
    py::object          m_bool_cls;
    py::object          m_int_cls;
    py::object          m_float_cls;
    py::object          m_complex_cls;
    py::object          m_str_cls;
    py::object          m_list_cls;
    py::object          m_tuple_cls;
    py::object          m_dict_cls;
    py::object          f_dict_get;
    py::object          m_bytes_cls;
    py::object          m_datetime_cls;
    py::object          m_date_cls;
    py::object          f_fromisoformat;

    //-- 10x related stuff
    py::object          m_xnone;
    py::object          m_nucleus_class;
    py::object          m_anonymous_class;
    py::object          m_traitable_id_class;
    py::object          m_trait_method_error_class;
    py::object          f_find_class;
    py::object          f_find_class_id;

    py::args            m_choices_args;
    py::args            m_style_sheet_args;

    py::object          m_rc_true;

    std::streambuf      *m_py_stream_buf = nullptr;
    std::streambuf      *m_std_stream_buf = nullptr;

    void get_rc_true();
    void get_anonymous_class();

    void create_choices_args() {
        m_choices_args = py::make_tuple(m_xnone, py::str("__choices"));
    }

    void create_style_sheet_args() {
        m_style_sheet_args = py::make_tuple(m_xnone, py::str("__style_sheet"));
    }

    static void add_to_py_path(const std::string& path);

public:
    static PyLinkage*   s_py_linkage;

    static void init(const std::string& path_to_package);

    explicit PyLinkage(const std::string& path_to_package);
    ~PyLinkage();

    static py::object type(const py::object& v) { return py::reinterpret_borrow<py::object>(v.get_type()); }

    static py::object type_class()              { return s_py_linkage->m_type_cls; }
    static py::object bool_class()              { return s_py_linkage->m_bool_cls; }
    static py::object int_class()               { return s_py_linkage->m_int_cls; }
    static py::object float_class()             { return s_py_linkage->m_float_cls; }
    static py::object complex_class()           { return s_py_linkage->m_complex_cls; }
    static py::object str_class()               { return s_py_linkage->m_str_cls; }
    static py::object bytes_class()             { return s_py_linkage->m_bytes_cls; }

    static py::object datetime_class()          { return s_py_linkage->m_datetime_cls; }
    static py::object date_class()              { return s_py_linkage->m_date_cls; }
    static py::object fromisoformat(const py::object& text) { return s_py_linkage->f_fromisoformat(text); }

    static py::object list_class()              { return s_py_linkage->m_list_cls; }
    static py::object tuple_class()             { return s_py_linkage->m_tuple_cls; }
    static py::object dict_class()              { return s_py_linkage->m_dict_cls; }

    static py::object dict_get(const py::dict& d, const py::object& key) {
        return s_py_linkage->f_dict_get(d, key, XNone());
    }

    static py::object XNone()                   { return s_py_linkage->m_xnone; }
    static py::object nucleus_class()           { return s_py_linkage->m_nucleus_class; }
    static const py::args& choices_args()       { return s_py_linkage->m_choices_args; }
    static const py::args& style_sheet_args()   { return s_py_linkage->m_style_sheet_args; }

    static const py::object& RC_TRUE() {
        if (!s_py_linkage->m_rc_true)
            s_py_linkage->get_rc_true();
        return s_py_linkage->m_rc_true;
    }

    static const py::object& anonymous_class() {
        if (!s_py_linkage->m_anonymous_class)
            s_py_linkage->get_anonymous_class();
        return s_py_linkage->m_anonymous_class;
    }

    static bool issubclass(const py::object& cls, const py::object& base_class) {
        //py::object base_type = py::type::of<BNucleus>();
        int res = PyObject_IsSubclass(cls.ptr(), base_class.ptr());
        if (res == -1)
            throw py::error_already_set();
        return res == 1;
    }

    static py::object traitable_id(const py::object& id_value, const py::object& coll_name) {
        return s_py_linkage->m_traitable_id_class(id_value, coll_name);
    }

    static py::object find_class(const py::str& class_id) {
        return s_py_linkage->f_find_class(class_id);
    }

    static py::object find_class_id(const py::object& cls) {
        return s_py_linkage->f_find_class_id(cls);
    }

    static std::size_t python_id(const py::object& obj) {
        return py::module_::import("builtins").attr("id")(obj).cast<std::size_t>();
    }

    static py::object pickle(const py::object& data) {
        try {
            return py::module_::import("pickle").attr("dumps")(data);
        }
        catch (const py::error_already_set& e) {
            throw py::value_error(py::str("Failed to pickle\n{}").format(e.what()));
        }
    }

    static py::object unpickle(const py::object& data) {
        try {
            return py::module_::import("pickle").attr("loads")(data);
        }
        catch (const py::error_already_set& e) {
            throw py::value_error(py::str("Failed to unpickle\n{}").format(e.what()));
        }
    }

    // will throw if class_module.class_name is not importable
    static bool is_instance(const py::object& obj, const char* py_class_module, const char* py_class_name) {
        py::object py_class = py::module_::import(py_class_module).attr(py_class_name);
        return py::isinstance(obj, py_class);
    }

    static void clear() {
        delete s_py_linkage;
    }

    static py::object create_trait_method_error(
        BTraitable* obj,
        const py::str& trait_name,
        const py::object& method_name,
        const py::object* value = nullptr,
        const py::args* args = nullptr,
        const py::error_already_set* other_exc = nullptr
    );

    void redirect_stdout_to_python();

};

