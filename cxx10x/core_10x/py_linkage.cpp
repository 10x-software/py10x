//
// Created by AMD on 12/17/2024.
//

#include <cstdio>
#include <iostream>

#include "py_linkage.h"
#include "btraitable.h"

PyLinkage* PyLinkage::s_py_linkage = nullptr;

void PyLinkage::init(const std::string &path_to_package) {
    assert(!s_py_linkage);
    s_py_linkage = new PyLinkage(path_to_package);
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
    auto mname = "core_10x.traitable";
    try {
        py::module_ mod = py::module_::import(mname);
        //py::module_ mod = import_module(mname);
        m_anonymous_class = mod.attr("AnonymousTraitable");
    }
    catch (const py::error_already_set&) {
        throw py::value_error(py::str("Failed to import module: {}").format(py::str(mname)));
    }
}

void PyLinkage::get_rc_true() {
    auto mname = "core_10x.rc";
    try {
        py::module_ mod = py::module_::import(mname);
        //py::module_ mod = import_module(mname);
        m_rc_true = mod.attr("RC_TRUE");
    }
    catch (const py::error_already_set&) {
        throw py::value_error(py::str("Failed to import module: {}").format(py::str(mname)));
    }
}


PyLinkage::PyLinkage(const std::string& path_to_package) {
    redirect_stdout_to_python();

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
    m_bytes_cls     = builtins.attr("bytes");

    py::module_ dt = py::module_::import("datetime");
    m_datetime_cls  = dt.attr("datetime");
    m_date_cls      = dt.attr("date");
    f_fromisoformat = m_date_cls.attr("fromisoformat");

    //add_to_py_path(path_to_package);

    const char* mname;
    py::module_ mod;
    try {
        mname = "core_10x.xnone";
        mod = py::module_::import(mname);
        m_xnone = mod.attr("XNone");

        mname = "core_10x.nucleus";
        mod = py::module_::import(mname);
        m_nucleus_class = mod.attr("Nucleus");

        mname = "core_10x.traitable_id";
        mod = py::module_::import(mname);
        m_traitable_id_class = mod.attr("ID");

        mname = "core_10x.trait_method_error";
        mod = py::module_::import(mname);
        m_trait_method_error_class = mod.attr("TraitMethodError");

        mname = "core_10x.package_refactoring";
        mod = py::module_::import(mname);
        auto pf_class = mod.attr("PackageRefactoring");
        f_find_class = pf_class.attr("find_class");
        f_find_class_id = pf_class.attr("find_class_id");
    }
    catch (const py::error_already_set&) {
        throw py::value_error(py::str("Failed to import module: {}").format(py::str(mname)));
    }

    create_choices_args();
    create_style_sheet_args();
}

PyLinkage::~PyLinkage() {
    if (m_std_stream_buf) {
        std::cout.rdbuf(m_std_stream_buf);
        delete m_py_stream_buf;
    }
}

py::object PyLinkage::create_trait_method_error(
        BTraitable* obj,
        const py::str& trait_name,
        const py::object& method_name,
        const py::object* value,
        const py::args* args,
        const py::error_already_set* other_exc
) {
    auto create = s_py_linkage->m_trait_method_error_class.attr("create");
    auto py_value = value ? *value : s_py_linkage->m_xnone;
    auto py_args = args? *args : py::args();
    auto py_other_exc = other_exc ? other_exc->value() : py::none();

    return create(obj, trait_name, method_name, py_value, py_args, py_other_exc);
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

    if (!m_std_stream_buf) {
        m_std_stream_buf = std::cout.rdbuf();
        auto py_buf = new PyStreamBuffer(write, flush);
        m_py_stream_buf = py_buf;
        std::cout.rdbuf(py_buf);
    }
}
