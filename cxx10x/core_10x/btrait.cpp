//
// Created by AMD on 3/19/2024.
//

#include "py_linkage.h"

#include "btrait.h"
#include "btraitable.h"
#include "btraitable_processor.h"

BTrait::BTrait() {
    m_datatype  = PyLinkage::XNone();
    m_default   = PyLinkage::XNone();
    m_getter_has_args = false;

    f_get           = py::none();
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

    m_proc = new BTraitProcessor();
}

py::error_already_set BTrait::trait_error(const py::error_already_set &exc, BTraitable *obj, const BTraitableClass *cls, const py::object& f, const py::object* value, const py::args* args) const {
    auto py_exc = PyLinkage::create_trait_method_error(obj, cls, name(), f.attr("__name__"), value, args, &exc);
    PyErr_SetObject(py_exc.get_type().ptr(), py_exc.ptr());
    return {};
}

py::object BTrait::wrapper_f_get(BTraitable* obj) const {
    try {
        return f_get(obj);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_get, nullptr, nullptr);
    }
}

py::object BTrait::wrapper_f_get(BTraitable* obj, const py::args& args) const {
    try {
        return f_get(obj, *args);
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
    if (getter_has_args())
        return PyLinkage::RC_TRUE();

    auto value = obj->get_value(this);
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

py::object BTrait::wrapper_f_style_sheet(BTraitable *obj) const {
    if (!f_style_sheet)
        return PyLinkage::XNone();

    try {
        return f_style_sheet(obj);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_style_sheet, nullptr, nullptr);
    }
}

