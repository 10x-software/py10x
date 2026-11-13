//
// Created by AMD on 3/19/2024.
//

#include "py_linkage.h"

#include "btrait.h"
#include "btraitable.h"
#include "btraitable_processor.h"

bool BTrait::s_use_instrumented_getters = false;

BTrait::BTrait() {
    m_datatype  = PyLinkage::XNone();
    m_default   = PyLinkage::XNone();
    m_getter_has_args = false;

    f_get               = py::none();
    f_get_instrumented  = py::none();

    f_set           = py::none();
    f_verify        = py::none();
    f_from_str      = py::none();
    f_from_any_xstr = py::none();
    f_to_str        = py::none();
    f_serialize     = py::none();
    f_deserialize   = py::none();
    f_to_id         = py::none();
}

void BTrait::create_proc() {
    if (flags_on(BTraitFlags::EVAL_ONCE))
        m_proc = new EvalOnceProc();
    else
        m_proc = new BTraitProcessor();
}

py::error_already_set BTrait::trait_error(const py::error_already_set &exc, BTraitable *obj, const BTraitableClass *cls, const py::object& f, const py::object* value, const py::args* args) const {
    auto py_exc = PyLinkage::create_trait_method_error(obj, cls, name(), f.attr("__name__"), value, args, &exc);
    PyErr_SetObject(py::type::handle_of(py_exc).ptr(), py_exc.ptr());
    return {};
}

py::object BTrait::wrapper_f_get(BTraitable* obj) const {
    try {
        //-- f_get_instrumented may be unset (this trait was never actually instrumented) even
        // while instrumentation is active process-wide elsewhere -- fall back to f_get rather
        // than calling None.
        bool use_instrumented = s_use_instrumented_getters && !f_get_instrumented.is_none();
        return use_instrumented ? f_get_instrumented(obj) : f_get(obj);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_get, nullptr, nullptr);
    }
}

py::object BTrait::wrapper_f_get(BTraitable* obj, const py::args& args) const {
    try {
        bool use_instrumented = s_use_instrumented_getters && !f_get_instrumented.is_none();
        return use_instrumented ? f_get_instrumented(obj, *args) : f_get(obj, *args);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_get, nullptr, &args);
    }
}

py::object BTrait::wrapper_f_set(BTraitable* obj, const py::object& value) const {
    try {
        return f_set(obj, this, value);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_set, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_set(BTraitable* obj, const py::object& value, const py::args& args) const {
    try {
        return f_set(obj, this, value, *args);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_set, &value, &args);
    }
}

py::object BTrait::wrapper_f_verify(BTraitable* obj) const {
    if (f_verify.is_none() || getter_has_args())
        return PyLinkage::RC_TRUE();

    const auto value = obj->get_value(this);
    return wrapper_f_verify(obj, value);
}

py::object BTrait::wrapper_f_verify(BTraitable* obj, const py::object& value) const {
    if (f_verify.is_none())
        return PyLinkage::RC_TRUE();

    try {
        return f_verify(obj, this, value);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_verify, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_from_str(BTraitable* obj, const py::object& value) const {
    try {
        auto res = f_from_str(obj, this, value);
        if (res.is(PyLinkage::XNone()))
            throw py::type_error(py::str("{}.{} - failed to convert from '{}'")
            .format(obj->class_name(), name(), value));

        return res;
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_from_str, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_from_any_xstr(BTraitable* obj, const py::object& value) const {
    try {
        auto res = f_from_any_xstr(obj, this, value);
        if (res.is(PyLinkage::XNone()))
            throw py::type_error(py::str("{}.{} - failed to convert from '{}'")
                                         .format(obj->class_name(), name(), value));
        return res;
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_from_any_xstr, &value, nullptr);
    }
}

bool BTrait::wrapper_f_is_acceptable_type(BTraitable* obj, const py::object& value) const {
    try {
        auto res = f_is_acceptable_type(obj, this, value);
        return py::cast<bool>(res);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_is_acceptable_type, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_to_str(BTraitable* obj, const py::object& value) const {
    try {
        return f_to_str(obj, this, value);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_to_str, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_serialize(const BTraitableClass* cls, const py::object& value) const {
    try {
        return f_serialize(this, value);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, cls, f_serialize, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_deserialize(const BTraitableClass* cls, const py::object& value) const {
    try {
        return f_deserialize(this, value);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, cls, f_deserialize, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_to_id(BTraitable* obj, const py::object& value) const {
    try {
        return f_to_id(obj, this, value);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_to_id, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_choices(BTraitable *obj) const {
    try {
        return f_choices(obj, this);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_choices, nullptr, nullptr);
    }
}

py::object BTrait::shallow_copy(const py::object& value) const {
    //-- only a value of the trait's own data type is copied: XNone, None and a mistyped value pass as they are
    if (!f_shallow_copy || !py::isinstance(value, m_datatype))
        return value;

    try {
        return f_shallow_copy(this, value);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, nullptr, nullptr, f_shallow_copy, &value, nullptr);
    }
}

py::object BTrait::deep_copy(const py::object& value) const {
    //-- as shallow_copy: only a value of the trait's own data type is copied
    if (!f_deep_copy || !py::isinstance(value, m_datatype))
        return value;

    try {
        return f_deep_copy(this, value);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, nullptr, nullptr, f_deep_copy, &value, nullptr);
    }
}

namespace {
    bool is_container(PyObject* value) {
        const auto type = Py_TYPE(value);   //-- the built-in types only: a subclass may hold more than its items
        return type == &PyList_Type || type == &PyDict_Type || type == &PySet_Type || type == &PyTuple_Type;
    }

    //-- a new reference, or nullptr with the Python error set
    PyObject* copy_of(PyObject* value) {
        const auto type = Py_TYPE(value);
        if (type == &PySet_Type)
            return PySet_New(value);    //-- what a set holds is hashable: nothing in it can change in place

        if (Py_EnterRecursiveCall(" while copying a container"))    //-- a container that holds itself ends here, not in a stack overflow
            return nullptr;

        //-- the level is copied first, in one C call, and only the copy is walked: nothing can change it underneath
        PyObject* res = nullptr;
        bool ok = true;
        if (type == &PyList_Type) {
            res = PyList_GetSlice(value, 0, PyList_GET_SIZE(value));
            for (Py_ssize_t i = 0, n = res ? PyList_GET_SIZE(res) : 0; ok && i < n; ++i) {
                const auto item = PyList_GET_ITEM(res, i);
                if (!is_container(item))
                    continue;

                const auto copied = copy_of(item);
                ok = copied && PyList_SetItem(res, i, copied) == 0;     //-- takes over copied, lets go of item
            }
        } else if (type == &PyDict_Type) {
            res = PyDict_Copy(value);
            PyObject *key, *item;
            for (Py_ssize_t pos = 0; ok && res && PyDict_Next(res, &pos, &key, &item); ) {
                if (!is_container(item))
                    continue;

                const auto copied = copy_of(item);
                ok = copied && PyDict_SetItem(res, key, copied) == 0;   //-- a value of an existing key: allowed while iterating
                Py_XDECREF(copied);
            }
        } else {    //-- a tuple cannot change, but a list in it can: a new tuple only if something in it was copied
            const auto n = PyTuple_GET_SIZE(value);
            for (Py_ssize_t i = 0; ok && i < n; ++i) {
                const auto item = PyTuple_GET_ITEM(value, i);
                if (!is_container(item))
                    continue;

                const auto copied = copy_of(item);
                if (!copied || copied == item) {
                    ok = copied != nullptr;
                    Py_XDECREF(copied);
                    continue;
                }
                if (!res) {
                    res = PyTuple_New(n);
                    for (Py_ssize_t j = 0; res && j < n; ++j) {
                        const auto same = PyTuple_GET_ITEM(value, j);
                        Py_INCREF(same);
                        PyTuple_SET_ITEM(res, j, same);
                    }
                }
                if (res)
                    ok = PyTuple_SetItem(res, i, copied) == 0;          //-- takes over copied, even when it fails
                else {
                    Py_DECREF(copied);
                    ok = false;
                }
            }
            if (ok && !res) {
                Py_INCREF(value);
                res = value;
            }
        }
        Py_LeaveRecursiveCall();

        if (ok && res)
            return res;

        Py_XDECREF(res);
        return nullptr;
    }
}

py::object BTrait::copy_containers(const py::object& value) {
    if (!is_container(value.ptr()))
        return value;

    const auto res = copy_of(value.ptr());
    if (!res)
        throw py::error_already_set();
    return py::reinterpret_steal<py::object>(res);
}

py::object BTrait::wrapper_f_style_sheet(BTraitable *obj) const {
    if (!f_style_sheet)
        return PyLinkage::XNone();

    try {
        return f_style_sheet(obj);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_style_sheet, nullptr, nullptr);
    }
}

