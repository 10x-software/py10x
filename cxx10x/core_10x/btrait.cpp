//
// Created by AMD on 3/19/2024.
//

#include "py_linkage.h"

#include "btrait.h"
#include "btraitable.h"
#include "btraitable_processor.h"
#include "bcache.h"
#include "brc.h"

BTrait::BTrait() {
    m_datatype  = PyLinkage::XNone();
    m_default   = PyLinkage::XNone();

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

py::error_already_set BTrait::trait_error(py::error_already_set &exc, BTraitable *obj, const py::object& f, const py::object* value, const py::args* args) {
    auto py_exc = PyLinkage::create_trait_method_error(obj, this, f.attr("__name__"), value, args, &exc);
    PyErr_SetObject(py_exc.get_type().ptr(), py_exc.ptr());
    return {};
}

py::object BTrait::wrapper_f_get(BTraitable* obj) {
    try {
        return f_get(obj);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_get, nullptr, nullptr);
    }
}

py::object BTrait::wrapper_f_get(BTraitable* obj, const py::args& args) {
    try {
        return f_get(obj, *args);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_get, nullptr, &args);
    }
}

py::object BTrait::wrapper_f_set(BTraitable* obj, const py::object& value) {
    try {
        return f_set(obj, this, value);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_set(BTraitable* obj, const py::object& value, const py::args& args) {
    try {
        return f_set(obj, this, value, *args);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_get, &value, &args);
    }
}

py::object BTrait::wrapper_f_verify(BTraitable* obj, const py::object& value) {
    try {
        return f_verify(obj, value);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_from_str(BTraitable* obj, const py::object& value) {
    try {
        auto res = f_from_str(obj, this, value);
        if (res.is(PyLinkage::XNone()))
            throw py::type_error(py::str("{}.{} - failed to convert from '{}'")
            .format(obj->class_name(), name(), value));

        return res;
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_from_any_xstr(BTraitable* obj, const py::object& value) {
    try {
        auto res = f_from_any_xstr(obj, this, value);
        if (res.is(PyLinkage::XNone()))
            throw py::type_error(py::str("{}.{} - failed to convert from '{}'")
                                         .format(obj->class_name(), name(), value));
        return res;
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_to_str(BTraitable* obj, const py::object& value) {
    try {
        return f_to_str(obj, this, value);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_serialize(BTraitable* obj, const py::object& value) {
    try {
        return f_serialize(obj, this, value);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_deserialize(BTraitable* obj, const py::object& value) {
    try {
        return f_deserialize(obj, this, value);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_to_id(BTraitable* obj, const py::object& value) {
    try {
        return f_to_id(obj, this, value);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_get, &value, nullptr);
    }
}

py::object BTrait::wrapper_f_choices(BTraitable *obj) {
    try {
        return f_choices(obj, this);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_choices, nullptr, nullptr);
    }
}

py::object BTrait::wrapper_f_style_sheet(BTraitable *obj)  {
    if (!f_style_sheet)
        return PyLinkage::empty_str();

    try {
        return f_style_sheet(obj);
    } catch (py::error_already_set& exc) {
        throw trait_error(exc, obj, f_style_sheet, nullptr, nullptr);
    }
}

//======================================================================================================================
//  Regular Trait
//======================================================================================================================

BasicNode* BTrait::find_node(BTraitableProcessor* proc, BTraitable* obj) {
    return proc->cache()->find_node(obj->tid(), this);
}

BasicNode* BTrait::find_node(BTraitableProcessor* proc, BTraitable* obj, const py::args& args) {
    return proc->cache()->find_node(obj->tid(), this, args);
}

BasicNode* BTrait::find_or_create_node(BTraitableProcessor* proc, BTraitable* obj, int node_type) {
    return proc->cache()->find_or_create_node(obj->tid(), this);
}

BasicNode* BTrait::find_or_create_node(BTraitableProcessor* proc, BTraitable* obj, int node_type, const py::args& args) {
    return proc->cache()->find_or_create_node(obj->tid(), this, args);
}


