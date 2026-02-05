//
// Created by AMD on 12/17/2024.
//

#include <cstdio>
#include <iostream>

#include "py_linkage.h"
#include "btraitable.h"

PyLinkage* PyLinkage::s_py_linkage = nullptr;

std::streambuf* PyLinkage::s_py_stream_buf = nullptr;
std::streambuf* PyLinkage::s_std_stream_buf = nullptr;


void PyLinkage::init(const py::dict& package_names) {
    assert(!s_py_linkage);
    redirect_stdout_to_python();

    s_py_linkage = new PyLinkage(package_names);
}

void PyLinkage::add_to_py_path(const std::string& path) {
    py::module_ sys = py::module_::import("sys");
    py::list sys_path = sys.attr("path");

    //for (auto item : sys_path) {
    //    std::cout << item.cast<std::string>() << std::endl;
    //}

    sys_path.append(path);
}

void check_threads(const std::string& label, const char* name) {
    std::cout << label << " " << name << " - thread ID: " << std::this_thread::get_id() << std::endl;
}

py::module_ import_module(const char* module_name) {
    check_threads("Before import", module_name);
    py::gil_scoped_acquire gil;
    auto module = py::module_::import(module_name);
    check_threads("After import", module_name);
    return module;
}

void PyLinkage::get_anonymous_class() {
    const auto mname = name_from_dict(CORE_10X::ANONYMOUS_MODULE_NAME, true);
    try {
        const py::module_ mod = py::module_::import(mname.c_str());
        m_anonymous_class = mod.attr(name_from_dict(CORE_10X::ANONYMOUS_CLASS_NAME).c_str());
    }
    catch (py::error_already_set& exc) {
        const auto msg = py::str("Failed to import module: {}").format(py::str(mname));
        py::raise_from(exc, PyExc_ValueError, msg.cast<std::string>().c_str());
        throw py::error_already_set();
    }
}

void PyLinkage::get_rc_true() {
    const auto mname = name_from_dict(CORE_10X::RC_MODULE_NAME, true);
    try {
        const py::module_ mod = py::module_::import(mname.c_str());
        m_rc_true = mod.attr(name_from_dict(CORE_10X::RC_TRUE_NAME).c_str());
    }
    catch (py::error_already_set& exc) {
        const auto msg = py::str("Failed to import module: {}").format(py::str(mname));
        py::raise_from(exc, PyExc_ValueError, msg.cast<std::string>().c_str());
        throw py::error_already_set();
    }
}

std::string PyLinkage::name_from_dict(const CORE_10X& enum_key, bool module) {
    py::object key = py::cast(enum_key);
    auto name = m_package_names[key].cast<std::string>();
    if (!module)
        return name;

    std::string full_name;
    full_name.reserve(m_py_package_name.size() + 1 + name.size());
    full_name.append(m_py_package_name).append(".").append(name);
    return full_name;
}

PyLinkage::PyLinkage(const py::dict& package_names) {
    m_package_names = package_names;

    //-- caching builtins and the like

    py::module_ builtins = py::module_::import("builtins");
    m_type_cls  = builtins.attr("type");
    m_bool_cls  = builtins.attr("bool");
    m_int_cls   = builtins.attr("int");
    m_float_cls = builtins.attr("float");
    m_complex_cls   = builtins.attr("complex");
    m_str_cls       = builtins.attr("str");
    m_list_cls      = builtins.attr("list");
    m_tuple_cls     = builtins.attr("tuple");
    m_dict_cls      = builtins.attr("dict");
    f_dict_get      = m_dict_cls.attr("get");
    m_bytes_cls     = builtins.attr("bytes");
    m_classmethod_cls = builtins.attr("classmethod");

    py::module_ dt = py::module_::import("datetime");
    m_datetime_cls  = dt.attr("datetime");
    m_date_cls      = dt.attr("date");
    f_fromisoformat = m_date_cls.attr("fromisoformat");

    //add_to_py_path(path_to_package);

    //-- caching core_10x stuff (some will be cached lazily as requested due to import cycles)
    std::string mname;
    py::module_ mod;
    py::object pf_class;

    m_py_package_name = name_from_dict(CORE_10X::PACKAGE_NAME);
    try {
        mname = name_from_dict(CORE_10X::XNONE_MODULE_NAME, true);
        mod = py::module_::import(mname.c_str());
        m_xnone = mod.attr(name_from_dict(CORE_10X::XNONE_CLASS_NAME).c_str());

        mname = name_from_dict(CORE_10X::NUCLEUS_MODULE_NAME, true);
        mod = py::module_::import(mname.c_str());
        m_nucleus_class = mod.attr(name_from_dict(CORE_10X::NUCLEUS_CLASS_NAME).c_str());

        mname = name_from_dict(CORE_10X::TRAITABLE_ID_MODULE_NAME, true);
        mod = py::module_::import(mname.c_str());
        m_traitable_id_class = mod.attr(name_from_dict(CORE_10X::TRAITABLE_ID_CLASS_NAME).c_str());

        mname = name_from_dict(CORE_10X::TRAIT_METHOD_ERROR_MODULE_NAME, true);
        mod = py::module_::import(mname.c_str());
        m_trait_method_error_class = mod.attr(name_from_dict(CORE_10X::TRAIT_METHOD_ERROR_CLASS_NAME).c_str());

        mname = name_from_dict(CORE_10X::PACKAGE_REFACTORING_MODULE_NAME, true);
        mod = py::module_::import(mname.c_str());
        pf_class = mod.attr(name_from_dict(CORE_10X::PACKAGE_REFACTORING_CLASS_NAME).c_str());
    }
    catch (py::error_already_set& exc) {
        const auto msg = py::str("Failed to import module: {}").format(py::str(mname));
        py::raise_from(exc, PyExc_ValueError, msg.cast<std::string>().c_str());
        throw py::error_already_set();
    }

    try {
        f_find_class = pf_class.attr(name_from_dict(CORE_10X::PACKAGE_REFACTORING_FIND_CLASS).c_str());
        f_find_class_id = pf_class.attr(name_from_dict(CORE_10X::PACKAGE_REFACTORING_FIND_CLASS_ID).c_str());
    }
    catch (py::error_already_set& exc) {
        py::raise_from(exc, PyExc_ValueError, "Failed to cache pf_class methods");
        throw py::error_already_set();
    }

    create_choices_args();
    create_style_sheet_args();
}

py::object PyLinkage::create_trait_method_error(
        BTraitable* obj,
        const BTraitableClass* cls,
        const py::str& trait_name,
        const py::object& method_name,
        const py::object* value,
        const py::args* args,
        const py::error_already_set* other_exc
) {
    const auto create = s_py_linkage->m_trait_method_error_class.attr("create");
    auto py_value = value ? *value : s_py_linkage->m_xnone;
    auto py_args = args? *args : py::args();
    auto py_other_exc = other_exc ? other_exc->value() : py::none();
    auto py_cls = cls ? cls->py_class() : py::none();

    return create(obj, py_cls, trait_name, method_name, py_value, py_other_exc, py_args);
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

    if (!s_std_stream_buf) {
        s_std_stream_buf = std::cout.rdbuf();
        s_py_stream_buf = new PyStreamBuffer(write, flush);
        std::cout.rdbuf(s_py_stream_buf);
    }
}
